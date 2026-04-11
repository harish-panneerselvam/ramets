"""Tests for the genet database (core/db.py)."""

import json
import tempfile
from pathlib import Path

import pytest

from ramets.core.db import GenetDB, compress_graph, decompress_graph


@pytest.fixture
def db(tmp_path):
    """Create a fresh database for each test."""
    db_path = tmp_path / "store.db"
    db = GenetDB(db_path)
    db.init_schema()
    yield db
    db.close()


@pytest.fixture
def sample_graph():
    """A minimal graph for testing."""
    return {
        "nodes": [
            {"id": "a", "label": "ModuleA", "file_type": "code",
             "source_file": "src/a.py", "community": 0},
            {"id": "b", "label": "ModuleB", "file_type": "code",
             "source_file": "src/b.py", "community": 0},
            {"id": "c", "label": "ModuleC", "file_type": "code",
             "source_file": "src/c.py", "community": 1},
        ],
        "links": [
            {"source": "a", "target": "b", "relation": "calls"},
            {"source": "b", "target": "c", "relation": "imports"},
        ],
    }


class TestCompression:
    def test_roundtrip(self, sample_graph):
        """Compress → decompress preserves graph data."""
        blob = compress_graph(sample_graph)
        assert isinstance(blob, bytes)
        assert len(blob) < len(json.dumps(sample_graph).encode())  # smaller

        restored = decompress_graph(blob)
        assert restored == sample_graph

    def test_empty_graph(self):
        """Empty graph roundtrips."""
        empty = {"nodes": [], "links": []}
        assert decompress_graph(compress_graph(empty)) == empty


class TestGenetStorage:
    def test_store_and_load(self, db, sample_graph):
        """Store genet and load it back."""
        db.store_genet(sample_graph, "abc123")

        loaded = db.load_genet()
        assert loaded is not None
        assert loaded == sample_graph

    def test_genet_meta(self, db, sample_graph):
        """Genet metadata is correct."""
        db.store_genet(sample_graph, "abc123")

        meta = db.genet_meta()
        assert meta is not None
        assert meta["commit_sha"] == "abc123"
        assert meta["node_count"] == 3
        assert meta["edge_count"] == 2

    def test_load_empty(self, db):
        """Loading with no genet returns None."""
        assert db.load_genet() is None
        assert db.genet_meta() is None

    def test_replace_genet(self, db, sample_graph):
        """Storing a new genet replaces the old one."""
        db.store_genet(sample_graph, "abc123")
        new_graph = {"nodes": [{"id": "x", "label": "X"}], "links": []}
        db.store_genet(new_graph, "def456")

        loaded = db.load_genet()
        assert len(loaded["nodes"]) == 1
        assert db.genet_meta()["commit_sha"] == "def456"


class TestRametStorage:
    def test_store_and_load(self, db, sample_graph):
        """Store and load a ramet snapshot."""
        db.store_ramet("feat/auth", sample_graph, "abc123")

        loaded = db.load_ramet("feat/auth")
        assert loaded is not None
        assert loaded == sample_graph

    def test_load_missing(self, db):
        """Loading a non-existent ramet returns None."""
        assert db.load_ramet("nonexistent") is None

    def test_list_ramets(self, db, sample_graph):
        """List all cached ramets."""
        db.store_ramet("feat/a", sample_graph, "abc")
        db.store_ramet("feat/b", sample_graph, "def")

        ramets = db.list_ramets()
        assert len(ramets) == 2
        branches = {r["branch"] for r in ramets}
        assert branches == {"feat/a", "feat/b"}

    def test_delete_ramet(self, db, sample_graph):
        """Deleting a ramet removes snapshot, deltas, and branch entry."""
        db.store_ramet("feat/x", sample_graph, "abc")
        db.register_branch("feat/x")
        db.append_deltas("feat/x", "abc", [
            {"op": "add_node", "entity_type": "node", "entity_id": "new",
             "payload": {"id": "new", "label": "New"}},
        ])

        db.delete_ramet("feat/x")
        assert db.load_ramet("feat/x") is None
        assert db.delta_count("feat/x") == 0


class TestDeltas:
    def test_append_and_load(self, db):
        """Append deltas and load them back."""
        deltas = [
            {"op": "add_node", "entity_type": "node", "entity_id": "x",
             "payload": {"id": "x", "label": "X"}},
            {"op": "rm_edge", "entity_type": "edge", "entity_id": "a|b|calls"},
        ]
        db.append_deltas("feat/test", "abc", deltas)

        loaded = db.load_deltas("feat/test")
        assert len(loaded) == 2
        assert loaded[0]["op"] == "add_node"
        assert loaded[0]["payload"]["label"] == "X"
        assert loaded[1]["op"] == "rm_edge"
        assert "payload" not in loaded[1]

    def test_delta_count(self, db):
        """Delta count is accurate."""
        assert db.delta_count("feat/test") == 0

        db.append_deltas("feat/test", "abc", [
            {"op": "add_node", "entity_type": "node", "entity_id": "x"},
        ])
        assert db.delta_count("feat/test") == 1


class TestBranches:
    def test_register_and_list(self, db):
        """Register branches and list them."""
        db.register_branch("main")
        db.register_branch("feat/auth", merge_base="abc123")

        branches = db.list_branches()
        assert len(branches) == 2
        names = {b["name"] for b in branches}
        assert names == {"main", "feat/auth"}

    def test_register_idempotent(self, db):
        """Registering the same branch twice doesn't duplicate."""
        db.register_branch("main")
        db.register_branch("main")

        branches = db.list_branches()
        assert len(branches) == 1
