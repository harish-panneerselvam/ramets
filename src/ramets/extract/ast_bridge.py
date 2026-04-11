"""Thin wrapper around graphify's AST extraction.

graphify handles tree-sitter parsing across 20 languages.
We only call it, never reimplement it. If graphify's API changes,
this is the only file that needs updating.
"""

from __future__ import annotations

import json
from pathlib import Path


def extract_graph(repo_path: Path) -> dict:
    """Extract AST knowledge graph from a repository.

    Uses graphify's code-only extraction (no LLM, no semantic analysis).
    Returns the standard graph format: {nodes: [...], links: [...]}.

    Args:
        repo_path: Path to the repository root.

    Returns:
        Graph data dict with nodes and links.
    """
    try:
        from graphify.watch import _rebuild_code
        _rebuild_code(repo_path)

        # graphify writes to .claude/graphify-out/graph.json or graphify-out/graph.json
        graph_json = _find_graph_json(repo_path)
        if graph_json and graph_json.exists():
            return json.loads(graph_json.read_text())

    except ImportError:
        pass  # graphify not installed, try fallback

    except Exception:
        # graphify failed, try fallback
        pass

    # Fallback: try loading existing graph.json if available
    graph_json = _find_graph_json(repo_path)
    if graph_json and graph_json.exists():
        return json.loads(graph_json.read_text())

    # No graphify, no existing graph — return empty
    return {"nodes": [], "links": []}


def extract_incremental(repo_path: Path, changed_files: list[str]) -> dict:
    """Re-extract graph after specific files changed.

    For now, does a full rebuild. Future optimization: only re-parse
    changed files and merge with existing graph.

    Args:
        repo_path: Repository root.
        changed_files: List of changed file paths (relative to repo).

    Returns:
        Updated graph data dict.
    """
    # TODO: Incremental extraction — only re-parse changed files
    # For now, full rebuild is fast enough for <1000-file repos
    return extract_graph(repo_path)


def _find_graph_json(repo_path: Path) -> Path | None:
    """Find graph.json in known locations."""
    candidates = [
        repo_path / ".claude" / "graphify-out" / "graph.json",
        repo_path / "graphify-out" / "graph.json",
        repo_path / ".graphify" / "graph.json",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None
