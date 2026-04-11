"""Tests for Obsidian vault generation (obsidian/vault.py, config.py, layers.py)."""

import json

import pytest

from ramets.core.db import GenetDB
from ramets.decision.schema import Decision, Option
from ramets.decision.tracker import DecisionTracker
from ramets.obsidian.vault import sanitize_filename


@pytest.fixture
def db(tmp_path):
    """Create a fresh database with sample data."""
    db_path = tmp_path / "store.db"
    db = GenetDB(db_path)
    db.init_schema()
    yield db
    db.close()


@pytest.fixture
def sample_graph():
    return {
        "nodes": [
            {"id": "a", "label": "ModuleA", "file_type": "code", "community": 0},
            {"id": "b", "label": "ModuleB", "file_type": "code", "community": 0},
            {"id": "c", "label": "ModuleC", "file_type": "code", "community": 1},
        ],
        "links": [
            {"source": "a", "target": "b", "relation": "calls"},
            {"source": "b", "target": "c", "relation": "imports"},
        ],
    }


class TestSanitizeFilename:
    def test_normal_name(self):
        assert sanitize_filename("ModuleA") == "ModuleA"

    def test_special_chars(self):
        assert sanitize_filename('foo/bar:baz"qux') == "foo_bar_baz_qux"

    def test_long_name(self):
        long = "a" * 100
        result = sanitize_filename(long)
        assert len(result) <= 80

    def test_empty_name(self):
        assert sanitize_filename("") == "unnamed"

    def test_dots_stripped(self):
        assert sanitize_filename("...test...") == "test"


class TestVaultGeneration:
    def test_generates_base_notes(self, db, sample_graph, tmp_path):
        """Base layer notes are created for each node."""
        from unittest.mock import patch

        from ramets.obsidian.vault import generate_vault

        db.store_genet(sample_graph, "abc123")

        vault_dir = tmp_path / "vault"
        with patch("ramets.obsidian.vault.current_branch", return_value="main"):
            with patch("ramets.obsidian.vault.materialize", return_value=sample_graph):
                generate_vault(db, vault_dir)

        # Check base layer exists
        base_dir = vault_dir / "base"
        assert base_dir.exists()
        assert (base_dir / "C00").exists()
        assert (base_dir / "C01").exists()

        # Check node notes exist
        assert (base_dir / "C00" / "ModuleA.md").exists()
        assert (base_dir / "C00" / "ModuleB.md").exists()
        assert (base_dir / "C01" / "ModuleC.md").exists()

    def test_generates_index(self, db, sample_graph, tmp_path):
        """Index/MOC note is created."""
        from unittest.mock import patch

        from ramets.obsidian.vault import generate_vault

        db.store_genet(sample_graph, "abc123")

        vault_dir = tmp_path / "vault"
        with patch("ramets.obsidian.vault.current_branch", return_value="main"):
            with patch("ramets.obsidian.vault.materialize", return_value=sample_graph):
                generate_vault(db, vault_dir)

        index = vault_dir / "Index.md"
        assert index.exists()
        content = index.read_text()
        assert "ramets Knowledge Graph" in content
        assert "3 nodes" in content

    def test_generates_graph_settings(self, db, sample_graph, tmp_path):
        """Obsidian graph settings are created."""
        from unittest.mock import patch

        from ramets.obsidian.vault import generate_vault

        db.store_genet(sample_graph, "abc123")

        vault_dir = tmp_path / "vault"
        with patch("ramets.obsidian.vault.current_branch", return_value="main"):
            with patch("ramets.obsidian.vault.materialize", return_value=sample_graph):
                generate_vault(db, vault_dir)

        assert (vault_dir / ".obsidian" / "graph.json").exists()
        assert (vault_dir / ".obsidian" / "app.json").exists()

    def test_node_note_has_frontmatter(self, db, sample_graph, tmp_path):
        """Node notes have YAML frontmatter with metadata."""
        from unittest.mock import patch

        from ramets.obsidian.vault import generate_vault

        db.store_genet(sample_graph, "abc123")

        vault_dir = tmp_path / "vault"
        with patch("ramets.obsidian.vault.current_branch", return_value="main"):
            with patch("ramets.obsidian.vault.materialize", return_value=sample_graph):
                generate_vault(db, vault_dir)

        content = (vault_dir / "base" / "C00" / "ModuleA.md").read_text()
        assert content.startswith("---")
        assert "id: a" in content
        assert "community: 0" in content
        assert "layer/base" in content

    def test_node_note_has_links(self, db, sample_graph, tmp_path):
        """Node notes contain wikilinks to connected nodes."""
        from unittest.mock import patch

        from ramets.obsidian.vault import generate_vault

        db.store_genet(sample_graph, "abc123")

        vault_dir = tmp_path / "vault"
        with patch("ramets.obsidian.vault.current_branch", return_value="main"):
            with patch("ramets.obsidian.vault.materialize", return_value=sample_graph):
                generate_vault(db, vault_dir)

        content = (vault_dir / "base" / "C00" / "ModuleA.md").read_text()
        assert "[[ModuleB|ModuleB]]" in content

    def test_branch_layer_generated(self, db, sample_graph, tmp_path):
        """Branch delta layer is generated for changed nodes."""
        from unittest.mock import patch

        from ramets.obsidian.vault import generate_vault

        db.store_genet(sample_graph, "abc123")

        # Create a branch graph with additions
        branch_graph = {
            "nodes": sample_graph["nodes"]
            + [{"id": "d", "label": "ModuleD", "file_type": "code", "community": 2}],
            "links": sample_graph["links"] + [{"source": "a", "target": "d", "relation": "uses"}],
        }

        vault_dir = tmp_path / "vault"
        with patch("ramets.obsidian.vault.current_branch", return_value="feat/test"):
            with patch("ramets.obsidian.vault.materialize", return_value=branch_graph):
                with patch("ramets.obsidian.layers.materialize", return_value=branch_graph):
                    generate_vault(db, vault_dir)

        # Branch layer directory should exist
        branch_dir = vault_dir / "branch--feat--test"
        assert branch_dir.exists()
        assert (branch_dir / "_BRANCH_INFO.md").exists()

        info_content = (branch_dir / "_BRANCH_INFO.md").read_text()
        assert "feat/test" in info_content
        assert "+1 nodes" in info_content

    def test_decision_notes_generated(self, db, sample_graph, tmp_path):
        """Decision notes are written to the vault."""
        from unittest.mock import patch

        from ramets.obsidian.vault import generate_vault

        db.store_genet(sample_graph, "abc123")

        # Record a decision
        tracker = DecisionTracker(db)
        decision = Decision(
            branch="main",
            category="architecture",
            question="Which auth strategy?",
            options=[Option(label="JWT"), Option(label="Sessions")],
            chosen=0,
            rationale="Stateless",
        )
        tracker.record(decision)

        vault_dir = tmp_path / "vault"
        with patch("ramets.obsidian.vault.current_branch", return_value="main"):
            with patch("ramets.obsidian.vault.materialize", return_value=sample_graph):
                generate_vault(db, vault_dir)

        decisions_dir = vault_dir / "decisions"
        assert decisions_dir.exists()
        dec_files = list(decisions_dir.glob("dec_*.md"))
        assert len(dec_files) == 1

        content = dec_files[0].read_text()
        assert "Which auth strategy?" in content
        assert "JWT" in content
        assert "[CHOSEN]" in content


class Test3DConfig:
    def test_generates_plugin_dir(self, tmp_path):
        from ramets.obsidian.config import generate_3d_config

        communities = {0: [{"id": "a", "label": "A"}], 1: [{"id": "b", "label": "B"}]}
        generate_3d_config(tmp_path, communities)

        plugin_dir = tmp_path / ".obsidian" / "plugins" / "3d-graph"
        assert plugin_dir.exists()
        assert (plugin_dir / "manifest.json").exists()
        assert (plugin_dir / "data.json").exists()
        assert (plugin_dir / "styles.css").exists()

    def test_manifest_content(self, tmp_path):
        from ramets.obsidian.config import generate_3d_config

        generate_3d_config(tmp_path, {0: []})
        manifest = json.loads((tmp_path / ".obsidian" / "plugins" / "3d-graph" / "manifest.json").read_text())
        assert manifest["id"] == "3d-graph"
        assert manifest["name"] == "3D Graph"

    def test_community_color_groups(self, tmp_path):
        from ramets.obsidian.config import generate_3d_config

        communities = {0: [], 1: [], 2: []}
        generate_3d_config(tmp_path, communities)
        data = json.loads((tmp_path / ".obsidian" / "plugins" / "3d-graph" / "data.json").read_text())

        community_groups = [g for g in data["colorGroups"] if g["query"].startswith("tag:community")]
        assert len(community_groups) == 3

    def test_branch_color_groups(self, tmp_path):
        from ramets.obsidian.config import generate_3d_config

        generate_3d_config(tmp_path, {0: []}, branches=["feat/auth", "main"])
        data = json.loads((tmp_path / ".obsidian" / "plugins" / "3d-graph" / "data.json").read_text())

        branch_groups = [g for g in data["colorGroups"] if g["query"].startswith("tag:branch")]
        assert len(branch_groups) == 2

    def test_decision_color_groups(self, tmp_path):
        from ramets.obsidian.config import generate_3d_config

        generate_3d_config(tmp_path, {0: []})
        data = json.loads((tmp_path / ".obsidian" / "plugins" / "3d-graph" / "data.json").read_text())

        decision_groups = [g for g in data["colorGroups"] if "decision" in g["query"]]
        assert len(decision_groups) >= 1


class TestBranchLayers:
    def test_render_with_deltas(self, db, sample_graph, tmp_path):
        from unittest.mock import patch

        from ramets.obsidian.layers import render_branch_layers

        db.store_genet(sample_graph, "abc123")

        branch_graph = {
            "nodes": sample_graph["nodes"]
            + [{"id": "d", "label": "ModuleD", "file_type": "code", "community": 2}],
            "links": sample_graph["links"] + [{"source": "a", "target": "d", "relation": "uses"}],
        }

        vault_dir = tmp_path / "vault"
        vault_dir.mkdir()

        with patch("ramets.obsidian.layers.materialize", return_value=branch_graph):
            count = render_branch_layers(db, vault_dir, ["feat/new"], genet=sample_graph)

        assert count > 0
        branch_dir = vault_dir / "branch--feat--new"
        assert branch_dir.exists()
        assert (branch_dir / "_BRANCH_INFO.md").exists()

    def test_render_no_deltas(self, db, sample_graph, tmp_path):
        from unittest.mock import patch

        from ramets.obsidian.layers import render_branch_layers

        db.store_genet(sample_graph, "abc123")

        vault_dir = tmp_path / "vault"
        vault_dir.mkdir()

        with patch("ramets.obsidian.layers.materialize", return_value=sample_graph):
            count = render_branch_layers(db, vault_dir, ["main"], genet=sample_graph)

        assert count == 0

    def test_render_no_genet(self, db, tmp_path):
        from ramets.obsidian.layers import render_branch_layers

        vault_dir = tmp_path / "vault"
        vault_dir.mkdir()

        count = render_branch_layers(db, vault_dir, ["main"])
        assert count == 0
