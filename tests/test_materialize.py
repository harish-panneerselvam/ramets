"""Tests for materialization (core/materialize.py)."""

import pytest

from ramets.core.db import GenetDB
from ramets.core.materialize import diff_branches, to_networkx


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


class TestToNetworkx:
    def test_basic_conversion(self, sample_graph):
        """Converts graph data to NetworkX DiGraph."""
        G = to_networkx(sample_graph)
        assert G.number_of_nodes() == 3
        assert G.number_of_edges() == 2

    def test_node_attributes(self, sample_graph):
        """Nodes carry their attributes."""
        G = to_networkx(sample_graph)
        assert G.nodes["a"]["label"] == "ModuleA"
        assert G.nodes["c"]["community"] == 1

    def test_edge_attributes(self, sample_graph):
        """Edges carry their attributes."""
        G = to_networkx(sample_graph)
        assert G.edges["a", "b"]["relation"] == "calls"

    def test_empty_graph(self):
        """Empty graph converts to empty DiGraph."""
        G = to_networkx({"nodes": [], "links": []})
        assert G.number_of_nodes() == 0
        assert G.number_of_edges() == 0


class TestDiffBranches:
    def test_identical_branches(self, db, sample_graph):
        """Identical branches show no differences."""
        db.store_genet(sample_graph, "abc")
        db.store_ramet("branch-a", sample_graph, "abc")
        db.store_ramet("branch-b", sample_graph, "abc")

        result = diff_branches(db, "branch-a", "branch-b")
        assert "Added: 0" in result
        assert "Removed: 0" in result
        assert "Modified: 0" in result

    def test_added_nodes(self, db, sample_graph):
        """Detects nodes added in branch-b."""
        db.store_genet(sample_graph, "abc")
        db.store_ramet("branch-a", sample_graph, "abc")

        extended = {
            "nodes": sample_graph["nodes"]
            + [{"id": "d", "label": "ModuleD", "file_type": "code", "community": 2}],
            "links": sample_graph["links"],
        }
        db.store_ramet("branch-b", extended, "def")

        result = diff_branches(db, "branch-a", "branch-b")
        assert "Added: 1" in result
        assert "ModuleD" in result

    def test_removed_nodes(self, db, sample_graph):
        """Detects nodes removed in branch-b."""
        db.store_genet(sample_graph, "abc")
        db.store_ramet("branch-a", sample_graph, "abc")

        reduced = {
            "nodes": [n for n in sample_graph["nodes"] if n["id"] != "c"],
            "links": [link for link in sample_graph["links"] if link["target"] != "c"],
        }
        db.store_ramet("branch-b", reduced, "def")

        result = diff_branches(db, "branch-a", "branch-b")
        assert "Removed: 1" in result


class TestMaterializeRoundtrip:
    def test_genet_with_no_deltas(self, db, sample_graph):
        """With no deltas, materialize returns the genet directly."""
        db.store_genet(sample_graph, "abc")
        db.register_branch("main")

        # No deltas stored, should return genet
        from ramets.core.delta import apply_deltas

        genet = db.load_genet()
        deltas = db.load_deltas("main")
        assert deltas == []

        # apply_deltas with empty list should return genet-equivalent
        result = apply_deltas(genet, deltas)
        assert {n["id"] for n in result["nodes"]} == {"a", "b", "c"}

    def test_deltas_produce_correct_graph(self, db, sample_graph):
        """Stored deltas correctly reconstruct a branch graph."""
        db.store_genet(sample_graph, "abc")

        from ramets.core.delta import apply_deltas, compute_deltas

        branch_graph = {
            "nodes": [
                {"id": "a", "label": "ModuleA_v2", "file_type": "code", "community": 0},
                {"id": "b", "label": "ModuleB", "file_type": "code", "community": 0},
                {"id": "d", "label": "ModuleD", "file_type": "code", "community": 2},
            ],
            "links": [
                {"source": "a", "target": "b", "relation": "calls"},
                {"source": "a", "target": "d", "relation": "uses"},
            ],
        }

        deltas = compute_deltas(sample_graph, branch_graph)
        db.append_deltas("feat/test", "def456", deltas)

        # Reload from DB and apply
        loaded_deltas = db.load_deltas("feat/test")
        genet = db.load_genet()
        result = apply_deltas(genet, loaded_deltas)

        result_ids = {n["id"] for n in result["nodes"]}
        assert result_ids == {"a", "b", "d"}
        assert "c" not in result_ids

        # Check modified node
        node_a = next(n for n in result["nodes"] if n["id"] == "a")
        assert node_a["label"] == "ModuleA_v2"

    def test_delta_replace_not_accumulate(self, db, sample_graph):
        """Replacing deltas doesn't double-count operations."""
        db.store_genet(sample_graph, "abc")

        from ramets.core.delta import compute_deltas

        branch_graph = {
            "nodes": sample_graph["nodes"]
            + [{"id": "d", "label": "ModuleD", "file_type": "code", "community": 2}],
            "links": sample_graph["links"],
        }

        deltas = compute_deltas(sample_graph, branch_graph)

        # Simulate what the fixed update command does: clear then append
        db.append_deltas("feat/test", "abc", deltas)
        count_1 = db.delta_count("feat/test")

        # "Update" again — should replace, not accumulate
        db.conn.execute("DELETE FROM ramet_deltas WHERE branch = ?", ("feat/test",))
        db.conn.commit()
        db.append_deltas("feat/test", "def", deltas)
        count_2 = db.delta_count("feat/test")

        assert count_1 == count_2  # Same count, not doubled
