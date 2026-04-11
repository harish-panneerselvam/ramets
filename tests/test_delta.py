"""Tests for delta computation and application (core/delta.py)."""

import pytest

from ramets.core.delta import apply_deltas, compute_deltas


@pytest.fixture
def genet():
    """Base graph (genet)."""
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


class TestComputeDeltas:
    def test_identical_graphs(self, genet):
        """Identical graphs produce no deltas."""
        deltas = compute_deltas(genet, genet)
        assert deltas == []

    def test_added_node(self, genet):
        """Detects added nodes."""
        branch = {
            "nodes": genet["nodes"] + [
                {"id": "d", "label": "ModuleD", "file_type": "code", "community": 2},
            ],
            "links": genet["links"],
        }
        deltas = compute_deltas(genet, branch)
        add_nodes = [d for d in deltas if d["op"] == "add_node"]
        assert len(add_nodes) == 1
        assert add_nodes[0]["entity_id"] == "d"
        assert add_nodes[0]["payload"]["label"] == "ModuleD"

    def test_removed_node(self, genet):
        """Detects removed nodes."""
        branch = {
            "nodes": [n for n in genet["nodes"] if n["id"] != "c"],
            "links": [l for l in genet["links"] if l["target"] != "c"],
        }
        deltas = compute_deltas(genet, branch)
        rm_nodes = [d for d in deltas if d["op"] == "rm_node"]
        assert len(rm_nodes) == 1
        assert rm_nodes[0]["entity_id"] == "c"

    def test_modified_node(self, genet):
        """Detects modified nodes."""
        branch = {
            "nodes": [
                {"id": "a", "label": "ModuleA_v2", "file_type": "code", "community": 0},
                genet["nodes"][1],
                genet["nodes"][2],
            ],
            "links": genet["links"],
        }
        deltas = compute_deltas(genet, branch)
        mod_nodes = [d for d in deltas if d["op"] == "mod_node"]
        assert len(mod_nodes) == 1
        assert mod_nodes[0]["payload"]["label"] == "ModuleA_v2"

    def test_added_edge(self, genet):
        """Detects added edges."""
        branch = {
            "nodes": genet["nodes"],
            "links": genet["links"] + [
                {"source": "a", "target": "c", "relation": "uses"},
            ],
        }
        deltas = compute_deltas(genet, branch)
        add_edges = [d for d in deltas if d["op"] == "add_edge"]
        assert len(add_edges) == 1
        assert add_edges[0]["entity_id"] == "a|c|uses"

    def test_removed_edge(self, genet):
        """Detects removed edges."""
        branch = {
            "nodes": genet["nodes"],
            "links": [genet["links"][0]],  # keep only first edge
        }
        deltas = compute_deltas(genet, branch)
        rm_edges = [d for d in deltas if d["op"] == "rm_edge"]
        assert len(rm_edges) == 1
        assert rm_edges[0]["entity_id"] == "b|c|imports"


class TestApplyDeltas:
    def test_roundtrip(self, genet):
        """compute_deltas → apply_deltas reproduces the branch graph."""
        branch = {
            "nodes": [
                {"id": "a", "label": "ModuleA_v2", "file_type": "code", "community": 0},
                {"id": "d", "label": "ModuleD", "file_type": "code", "community": 2},
            ],
            "links": [
                {"source": "a", "target": "d", "relation": "calls"},
            ],
        }

        deltas = compute_deltas(genet, branch)
        reconstructed = apply_deltas(genet, deltas)

        # Same nodes (by id set)
        recon_ids = {n["id"] for n in reconstructed["nodes"]}
        branch_ids = {n["id"] for n in branch["nodes"]}
        assert recon_ids == branch_ids

        # Same edges
        recon_edges = {(e["source"], e["target"], e["relation"])
                       for e in reconstructed["links"]}
        branch_edges = {(e["source"], e["target"], e["relation"])
                        for e in branch["links"]}
        assert recon_edges == branch_edges

    def test_empty_deltas(self, genet):
        """No deltas returns graph identical to genet."""
        result = apply_deltas(genet, [])
        assert {n["id"] for n in result["nodes"]} == {n["id"] for n in genet["nodes"]}

    def test_no_mutation(self, genet):
        """apply_deltas doesn't mutate the input genet."""
        import copy
        original = copy.deepcopy(genet)

        deltas = [{"op": "add_node", "entity_type": "node", "entity_id": "x",
                    "payload": {"id": "x", "label": "X"}}]
        apply_deltas(genet, deltas)

        assert genet == original  # unchanged
