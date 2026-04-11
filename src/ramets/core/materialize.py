"""Materialize a branch graph from genet + deltas.

This is the core read path: load genet, apply branch deltas, return
a NetworkX DiGraph for querying. Caches the result as a ramet snapshot.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import networkx as nx

from ramets.core.branch import current_branch, current_commit
from ramets.core.db import GenetDB
from ramets.core.delta import apply_deltas


def materialize(db: GenetDB, branch: str | None = None) -> dict:
    """Materialize the full graph for a branch.

    Loads genet, applies branch deltas, caches as ramet snapshot.
    If the branch has no deltas, returns the genet directly.

    Args:
        db: The genet database.
        branch: Branch name. Defaults to current branch.

    Returns:
        Graph data dict {nodes: [...], links: [...]}.
    """
    if branch is None:
        branch = current_branch()

    # Check if we have a fresh cached ramet
    ramet = db.load_ramet(branch)
    if ramet is not None:
        return ramet

    # Load genet
    genet = db.load_genet()
    if genet is None:
        raise RuntimeError("No genet found. Run `ramets init` first.")

    # Load and apply deltas
    deltas = db.load_deltas(branch)
    if not deltas:
        return genet

    graph_data = apply_deltas(genet, deltas)

    # Cache as ramet
    commit_sha = current_commit()
    db.store_ramet(branch, graph_data, commit_sha)

    return graph_data


def to_networkx(graph_data: dict) -> nx.DiGraph:
    """Convert graph data dict to a NetworkX DiGraph.

    Nodes get all their attributes. Edges get relation, confidence, etc.
    """
    G = nx.DiGraph()

    for node in graph_data.get("nodes", []):
        nid = node.get("id", "")
        attrs = {k: v for k, v in node.items() if k != "id"}
        G.add_node(nid, **attrs)

    for edge in graph_data.get("links", []):
        src = edge.get("source", "")
        tgt = edge.get("target", "")
        attrs = {k: v for k, v in edge.items() if k not in ("source", "target")}
        G.add_edge(src, tgt, **attrs)

    return G


def query_graph(db: GenetDB, question: str, branch: str | None = None,
                depth: int = 3, token_budget: int = 2000) -> str:
    """Query the knowledge graph using keyword matching + BFS traversal.

    Args:
        db: The genet database.
        question: Natural language question.
        branch: Branch to query. Defaults to current.
        depth: BFS traversal depth.
        token_budget: Approximate token limit for response.

    Returns:
        Formatted string with relevant nodes and connections.
    """
    graph_data = materialize(db, branch)
    G = to_networkx(graph_data)

    # Simple keyword matching to find seed nodes
    keywords = _extract_keywords(question)
    seed_nodes = _find_seeds(G, keywords)

    if not seed_nodes:
        return f"No nodes matched query: {question}"

    # BFS from seeds up to depth
    visited: set[str] = set()
    result_lines: list[str] = []
    total_chars = 0

    for seed in seed_nodes[:5]:  # max 5 seeds
        for node in nx.bfs_tree(G, seed, depth_limit=depth):
            if node in visited:
                continue
            visited.add(node)

            attrs = G.nodes[node]
            label = attrs.get("label", node)
            source = attrs.get("source_file", "")
            community = attrs.get("community", "?")

            # Format node
            line = f"- [{label}] ({source}) C{community}"

            # Add edges
            edges_out = []
            for _, tgt, data in G.out_edges(node, data=True):
                rel = data.get("relation", "->")
                tgt_label = G.nodes.get(tgt, {}).get("label", tgt)
                edges_out.append(f"  {rel} -> {tgt_label}")

            node_text = line + "\n" + "\n".join(edges_out[:5])
            total_chars += len(node_text)

            # Approximate token budget (1 token ~ 4 chars)
            if total_chars > token_budget * 4:
                result_lines.append(f"... (truncated at {token_budget} token budget)")
                break

            result_lines.append(node_text)

    header = f"## Graph query: {question}\n"
    header += f"Branch: {branch or current_branch()} | "
    header += f"Seeds: {len(seed_nodes)} | Traversed: {len(visited)} nodes\n"
    return header + "\n".join(result_lines)


def diff_branches(db: GenetDB, branch_a: str, branch_b: str) -> str:
    """Show graph differences between two branches.

    Returns a formatted string describing added/removed/modified nodes.
    """
    graph_a = materialize(db, branch_a)
    graph_b = materialize(db, branch_b)

    nodes_a = {n["id"]: n for n in graph_a.get("nodes", [])}
    nodes_b = {n["id"]: n for n in graph_b.get("nodes", [])}

    added = set(nodes_b.keys()) - set(nodes_a.keys())
    removed = set(nodes_a.keys()) - set(nodes_b.keys())
    modified = {
        nid for nid in nodes_a.keys() & nodes_b.keys()
        if nodes_a[nid] != nodes_b[nid]
    }

    lines = [f"## Graph diff: {branch_a} vs {branch_b}\n"]
    lines.append(f"Added: {len(added)} | Removed: {len(removed)} | Modified: {len(modified)}\n")

    if added:
        lines.append("### Added nodes")
        for nid in sorted(added)[:20]:
            label = nodes_b[nid].get("label", nid)
            lines.append(f"  + {label}")

    if removed:
        lines.append("### Removed nodes")
        for nid in sorted(removed)[:20]:
            label = nodes_a[nid].get("label", nid)
            lines.append(f"  - {label}")

    if modified:
        lines.append("### Modified nodes")
        for nid in sorted(modified)[:20]:
            label = nodes_b[nid].get("label", nid)
            lines.append(f"  ~ {label}")

    return "\n".join(lines)


def summary(db: GenetDB, branch: str | None = None) -> str:
    """Generate a compact summary for session injection (~400 tokens).

    This is what the SessionStart hook injects into Claude's context.
    """
    if branch is None:
        branch = current_branch()

    graph_data = materialize(db, branch)
    G = to_networkx(graph_data)

    node_count = G.number_of_nodes()
    edge_count = G.number_of_edges()

    # God nodes (top 10 by degree)
    degree = sorted(G.degree(), key=lambda x: -x[1])[:10]
    gods = "\n".join(
        f"  {G.nodes[n].get('label', n)} ({d} edges)" for n, d in degree
    )

    # Communities
    communities: defaultdict[int, list[str]] = defaultdict(list)
    for n, data in G.nodes(data=True):
        cid = data.get("community", -1)
        communities[cid].append(data.get("label", n))

    comm_lines = []
    for cid in sorted(communities)[:15]:
        members = communities[cid]
        comm_lines.append(f"  C{cid}: {len(members)} nodes (e.g. {members[0][:40]})")
    comm_summary = "\n".join(comm_lines)

    # Delta info
    delta_count = db.delta_count(branch)
    genet_meta = db.genet_meta()
    genet_commit = genet_meta["commit_sha"] if genet_meta else "unknown"

    return f"""## ramets: {branch} ({node_count} nodes, {edge_count} edges)
Genet: {genet_commit} | Deltas: {delta_count}

### God Nodes (most connected)
{gods}

### Communities (top 15 of {len(communities)})
{comm_summary}

### Usage
- Query: ramets query "question"
- Diff: ramets diff {branch} main
- Decisions: ramets decisions
- NEVER read graph blobs directly — use ramets query"""


# ── Internal helpers ───────────────────────────────────────────────

def _extract_keywords(question: str) -> list[str]:
    """Extract meaningful keywords from a question."""
    stop_words = {
        "how", "does", "what", "where", "is", "the", "a", "an", "in", "to",
        "of", "for", "with", "this", "that", "it", "from", "by", "on", "at",
        "and", "or", "not", "are", "was", "were", "be", "been", "do", "did",
        "can", "could", "would", "should", "will", "work", "works", "use",
        "used", "using",
    }
    words = question.lower().replace("?", "").replace("'", "").split()
    return [w for w in words if w not in stop_words and len(w) > 2]


def _find_seeds(G: nx.DiGraph, keywords: list[str], max_seeds: int = 10) -> list[str]:
    """Find nodes whose labels match query keywords."""
    scores: dict[str, int] = {}
    for node, data in G.nodes(data=True):
        label = (data.get("label", "") + " " + data.get("source_file", "")).lower()
        score = sum(1 for kw in keywords if kw in label)
        if score > 0:
            scores[node] = score

    return sorted(scores, key=lambda n: -scores[n])[:max_seeds]
