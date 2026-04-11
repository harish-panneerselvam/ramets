"""Tests for MCP tool graph operations (get_neighbors, shortest_path, get_community).

Tests the underlying graph logic using materialize + to_networkx directly,
without spinning up the FastMCP server.
"""

from __future__ import annotations

import networkx as nx
import pytest

from ramets.core.materialize import to_networkx


@pytest.fixture
def sample_graph():
    """Graph with 3 communities and clear paths."""
    return {
        "nodes": [
            {"id": "a", "label": "AuthHandler", "source_file": "auth.py", "community": 0},
            {"id": "b", "label": "UserModel", "source_file": "models.py", "community": 0},
            {"id": "c", "label": "Database", "source_file": "db.py", "community": 1},
            {"id": "d", "label": "Router", "source_file": "router.py", "community": 1},
            {"id": "e", "label": "Logger", "source_file": "logger.py", "community": 2},
        ],
        "links": [
            {"source": "a", "target": "b", "relation": "calls"},
            {"source": "a", "target": "c", "relation": "imports"},
            {"source": "b", "target": "c", "relation": "imports"},
            {"source": "d", "target": "a", "relation": "calls"},
            {"source": "c", "target": "e", "relation": "calls"},
        ],
    }


@pytest.fixture
def G(sample_graph):
    return to_networkx(sample_graph)


class TestGetNeighbors:
    def test_outgoing(self, G):
        succs = list(G.successors("a"))
        assert set(succs) == {"b", "c"}

    def test_incoming(self, G):
        preds = list(G.predecessors("a"))
        assert set(preds) == {"d"}

    def test_both_directions(self, G):
        preds = set(G.predecessors("a"))
        succs = set(G.successors("a"))
        all_neighbors = preds | succs
        assert all_neighbors == {"b", "c", "d"}

    def test_edge_relations(self, G):
        for _, t, d in G.out_edges("a", data=True):
            assert "relation" in d
            if t == "b":
                assert d["relation"] == "calls"
            if t == "c":
                assert d["relation"] == "imports"

    def test_leaf_node_no_outgoing(self, G):
        succs = list(G.successors("e"))
        assert succs == []

    def test_fuzzy_label_match(self, G):
        """Verify fuzzy label matching pattern used by MCP tools."""
        found = None
        for nid, data in G.nodes(data=True):
            if "auth" in data.get("label", "").lower():
                found = nid
                break
        assert found == "a"


class TestShortestPath:
    def test_direct_path(self, G):
        path = nx.shortest_path(G, "a", "b")
        assert path == ["a", "b"]

    def test_multi_hop_path(self, G):
        path = nx.shortest_path(G, "d", "e")
        # d -> a -> c -> e
        assert path == ["d", "a", "c", "e"]

    def test_no_path(self, G):
        with pytest.raises(nx.NetworkXNoPath):
            nx.shortest_path(G, "e", "d")

    def test_path_with_edge_data(self, G):
        path = nx.shortest_path(G, "a", "c")
        assert path == ["a", "c"]
        edge_data = G.get_edge_data("a", "c")
        assert edge_data["relation"] == "imports"

    def test_self_path(self, G):
        path = nx.shortest_path(G, "a", "a")
        assert path == ["a"]


class TestGetCommunity:
    def test_community_0(self, G):
        members = [nid for nid, data in G.nodes(data=True) if data.get("community") == 0]
        assert set(members) == {"a", "b"}

    def test_community_1(self, G):
        members = [nid for nid, data in G.nodes(data=True) if data.get("community") == 1]
        assert set(members) == {"c", "d"}

    def test_community_2(self, G):
        members = [nid for nid, data in G.nodes(data=True) if data.get("community") == 2]
        assert set(members) == {"e"}

    def test_nonexistent_community(self, G):
        members = [nid for nid, data in G.nodes(data=True) if data.get("community") == 99]
        assert members == []

    def test_internal_edges(self, G):
        """Count edges where both endpoints are in community 0."""
        c0_members = {nid for nid, data in G.nodes(data=True) if data.get("community") == 0}
        internal = sum(1 for u, v in G.edges() if u in c0_members and v in c0_members)
        # a -> b is the only edge within community 0
        assert internal == 1
