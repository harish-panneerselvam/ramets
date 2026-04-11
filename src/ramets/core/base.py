"""Genet builder — constructs the base (shared root) graph.

Wraps graphify's AST extraction to build the initial knowledge graph,
then stores it as a compressed blob in the genet table.
"""

from __future__ import annotations

from pathlib import Path

from ramets.core.branch import current_commit, get_repo_root
from ramets.core.db import GenetDB
from ramets.extract.ast_bridge import extract_graph


def build_genet(db: GenetDB, repo_path: Path | None = None) -> dict:
    """Build the base graph from the current HEAD and store it.

    Args:
        db: The genet database connection.
        repo_path: Repository root path. Defaults to current repo root.

    Returns:
        The graph data dict {nodes: [...], links: [...]}.
    """
    if repo_path is None:
        repo_path = get_repo_root()

    commit_sha = current_commit(cwd=repo_path)

    # Extract AST graph via graphify
    graph_data = extract_graph(repo_path)

    # Store as genet
    db.store_genet(graph_data, commit_sha)

    return graph_data


def load_genet_or_build(db: GenetDB, repo_path: Path | None = None) -> dict:
    """Load genet from DB, or build if it doesn't exist."""
    genet = db.load_genet()
    if genet is not None:
        return genet
    return build_genet(db, repo_path)
