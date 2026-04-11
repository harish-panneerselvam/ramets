"""Delta computation — diff a branch graph against the genet.

Produces a minimal set of operations (add/remove/modify nodes and edges)
that transform the genet into the branch-specific graph.
"""

from __future__ import annotations



def compute_deltas(genet: dict, branch_graph: dict) -> list[dict]:
    """Compute deltas that transform genet into branch_graph.

    Args:
        genet: Base graph {nodes: [...], links: [...]}.
        branch_graph: Branch-specific graph {nodes: [...], links: [...]}.

    Returns:
        List of delta operations, each with:
        - op: add_node, rm_node, mod_node, add_edge, rm_edge, mod_edge
        - entity_type: 'node' or 'edge'
        - entity_id: unique identifier
        - payload: full entity data (for add/mod) or None (for rm)
    """
    deltas: list[dict] = []

    # ── Node deltas ────────────────────────────────────────────────
    genet_nodes = {n["id"]: n for n in genet.get("nodes", [])}
    branch_nodes = {n["id"]: n for n in branch_graph.get("nodes", [])}

    # Added nodes (in branch but not in genet)
    for nid, node in branch_nodes.items():
        if nid not in genet_nodes:
            deltas.append({
                "op": "add_node",
                "entity_type": "node",
                "entity_id": nid,
                "payload": node,
            })

    # Removed nodes (in genet but not in branch)
    for nid in genet_nodes:
        if nid not in branch_nodes:
            deltas.append({
                "op": "rm_node",
                "entity_type": "node",
                "entity_id": nid,
            })

    # Modified nodes (in both, but different)
    for nid in genet_nodes:
        if nid in branch_nodes and genet_nodes[nid] != branch_nodes[nid]:
            deltas.append({
                "op": "mod_node",
                "entity_type": "node",
                "entity_id": nid,
                "payload": branch_nodes[nid],
            })

    # ── Edge deltas ────────────────────────────────────────────────
    genet_edges = _index_edges(genet.get("links", []))
    branch_edges = _index_edges(branch_graph.get("links", []))

    # Added edges
    for eid, edge in branch_edges.items():
        if eid not in genet_edges:
            deltas.append({
                "op": "add_edge",
                "entity_type": "edge",
                "entity_id": eid,
                "payload": edge,
            })

    # Removed edges
    for eid in genet_edges:
        if eid not in branch_edges:
            deltas.append({
                "op": "rm_edge",
                "entity_type": "edge",
                "entity_id": eid,
            })

    # Modified edges
    for eid in genet_edges:
        if eid in branch_edges and genet_edges[eid] != branch_edges[eid]:
            deltas.append({
                "op": "mod_edge",
                "entity_type": "edge",
                "entity_id": eid,
                "payload": branch_edges[eid],
            })

    return deltas


def apply_deltas(genet: dict, deltas: list[dict]) -> dict:
    """Apply deltas to a genet to produce a branch graph.

    Args:
        genet: Base graph {nodes: [...], links: [...]}.
        deltas: List of delta operations from compute_deltas or DB.

    Returns:
        The materialized branch graph.
    """
    # Deep copy genet to avoid mutation
    nodes = {n["id"]: dict(n) for n in genet.get("nodes", [])}
    edges = _index_edges(genet.get("links", []))

    for delta in deltas:
        op = delta["op"]
        eid = delta["entity_id"]
        payload = delta.get("payload")

        if op == "add_node":
            nodes[eid] = payload
        elif op == "rm_node":
            nodes.pop(eid, None)
        elif op == "mod_node":
            nodes[eid] = payload
        elif op == "add_edge":
            edges[eid] = payload
        elif op == "rm_edge":
            edges.pop(eid, None)
        elif op == "mod_edge":
            edges[eid] = payload

    return {
        "nodes": list(nodes.values()),
        "links": list(edges.values()),
    }


def _edge_key(edge: dict) -> str:
    """Create a unique key for an edge."""
    src = edge.get("source", "")
    tgt = edge.get("target", "")
    rel = edge.get("relation", "")
    return f"{src}|{tgt}|{rel}"


def _index_edges(edges: list[dict]) -> dict[str, dict]:
    """Index edges by their unique key."""
    return {_edge_key(e): e for e in edges}
