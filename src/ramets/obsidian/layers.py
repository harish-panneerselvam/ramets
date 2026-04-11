"""Branch layer rendering for Obsidian vault.

Generates per-branch folders showing only delta nodes (what changed).
Each branch gets a ``branch--<name>/`` folder with:
- ``_BRANCH_INFO.md`` — summary of adds/removes/modifies
- Individual notes for each added or modified node
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from ramets.core.db import GenetDB
from ramets.core.materialize import materialize
from ramets.obsidian.vault import RELATION_EMOJI, sanitize_filename


def render_branch_layers(
    db: GenetDB,
    vault_dir: Path,
    branches: list[str],
    genet: dict | None = None,
) -> int:
    """Render branch delta layers into the vault.

    Args:
        db: The genet database.
        vault_dir: Obsidian vault root directory.
        branches: Branch names to render.
        genet: Base graph data. If None, loaded from DB.

    Returns:
        Total number of notes written across all branches.
    """
    if genet is None:
        genet = db.load_genet()
    if not genet:
        return 0

    base_node_by_id = {n["id"]: n for n in genet.get("nodes", [])}
    base_id_to_filename = {n["id"]: sanitize_filename(n["label"]) for n in genet.get("nodes", [])}

    total = 0
    for branch in branches:
        total += _render_single_branch(
            db, vault_dir, branch, genet, base_id_to_filename, base_node_by_id
        )
    return total


def _render_single_branch(
    db: GenetDB,
    vault_dir: Path,
    branch: str,
    genet: dict,
    base_id_to_filename: dict,
    base_node_by_id: dict,
) -> int:
    """Render a single branch's delta layer. Returns note count."""
    from ramets.core.delta import compute_deltas

    branch_graph = materialize(db, branch)
    deltas = compute_deltas(genet, branch_graph)

    if not deltas:
        return 0

    branch_dir_name = re.sub(r"[/\\]", "--", branch)
    branch_dir = vault_dir / f"branch--{branch_dir_name}"
    branch_dir.mkdir(parents=True, exist_ok=True)

    # Categorize deltas
    added = [d for d in deltas if d["op"] == "add_node"]
    removed = [d for d in deltas if d["op"] == "rm_node"]
    modified = [d for d in deltas if d["op"] == "mod_node"]
    added_edges = [d for d in deltas if d["op"] == "add_edge"]
    removed_edges = [d for d in deltas if d["op"] == "rm_edge"]

    _write_branch_info(
        branch_dir, branch, branch_dir_name,
        added, removed, modified, added_edges, removed_edges,
        base_node_by_id,
    )

    # Build branch graph adjacency
    branch_nodes = {n["id"]: n for n in branch_graph.get("nodes", [])}
    outgoing: defaultdict[str, list[tuple[str, str]]] = defaultdict(list)
    incoming: defaultdict[str, list[tuple[str, str]]] = defaultdict(list)
    for link in branch_graph.get("links", []):
        src = link.get("source", "")
        tgt = link.get("target", "")
        rel = link.get("relation", "unknown")
        if src in branch_nodes and tgt in branch_nodes:
            outgoing[src].append((rel, tgt))
            incoming[tgt].append((rel, src))

    # Write notes for added/modified nodes
    note_count = 1  # _BRANCH_INFO.md
    changed_ids = {d["entity_id"] for d in added + modified}
    for nid in changed_ids:
        if nid not in branch_nodes:
            continue
        _write_delta_note(
            branch_dir, branch, branch_dir_name,
            nid, branch_nodes[nid],
            nid not in base_node_by_id,
            outgoing, incoming, branch_nodes,
        )
        note_count += 1

    return note_count


def _write_branch_info(
    branch_dir: Path,
    branch: str,
    branch_dir_name: str,
    added: list,
    removed: list,
    modified: list,
    added_edges: list,
    removed_edges: list,
    base_node_by_id: dict,
) -> None:
    """Write the _BRANCH_INFO.md summary note."""
    lines = [
        "---",
        f"branch: {branch}",
        f"tags: [layer/branch, branch/{branch_dir_name}]",
        "---",
        "",
        f"# Branch: {branch}",
        "",
        f"**+{len(added)} nodes** | **-{len(removed)} nodes** | "
        f"**~{len(modified)} modified** | "
        f"**+{len(added_edges)}/\u2013{len(removed_edges)} edges**",
        "",
    ]

    if added:
        lines.append("## Added Nodes")
        lines.append("")
        for d in added[:50]:
            label = d.get("payload", {}).get("label", d["entity_id"])
            fname = sanitize_filename(label)
            lines.append(f"- [[{fname}|{label}]]")
        lines.append("")

    if removed:
        lines.append("## Removed Nodes")
        lines.append("")
        for d in removed[:50]:
            eid = d["entity_id"]
            label = base_node_by_id.get(eid, {}).get("label", eid)
            lines.append(f"- ~~{label}~~")
        lines.append("")

    if modified:
        lines.append("## Modified Nodes")
        lines.append("")
        for d in modified[:50]:
            label = d.get("payload", {}).get("label", d["entity_id"])
            fname = sanitize_filename(label)
            lines.append(f"- [[{fname}|{label}]]")
        lines.append("")

    (branch_dir / "_BRANCH_INFO.md").write_text("\n".join(lines))


def _write_delta_note(
    branch_dir: Path,
    branch: str,
    branch_dir_name: str,
    nid: str,
    node: dict,
    is_new: bool,
    outgoing: dict,
    incoming: dict,
    branch_nodes: dict,
) -> None:
    """Write a single delta node note."""
    label = node.get("label", nid)
    filename = sanitize_filename(label)
    community = node.get("community", -1)
    file_type = node.get("file_type", "")
    source_file = node.get("source_file", "")

    lines = [
        "---",
        f"id: {nid}",
        f"type: {file_type}",
        f"community: {community}",
        f"change: {'added' if is_new else 'modified'}",
    ]
    if source_file:
        lines.append(f"source: {source_file}")
    tags = [
        f"community/C{community:02d}",
        f"type/{file_type or 'unknown'}",
        "layer/branch",
        f"branch/{branch_dir_name}",
        "delta/added" if is_new else "delta/modified",
    ]
    lines.append(f"tags: [{', '.join(tags)}]")
    lines.append("---")
    lines.append("")
    lines.append(f"# {'\U0001f195 ' if is_new else '\u270f\ufe0f '}{label}")
    lines.append("")
    lines.append(f"*{'Added' if is_new else 'Modified'} in `{branch}`*")
    lines.append("")

    if source_file:
        lines.append(f"**Source:** `{source_file}`")
        lines.append("")

    # Connections
    out = outgoing.get(nid, [])
    if out:
        lines.append("## Connects To")
        lines.append("")
        for rel, tid in out[:20]:
            tgt_label = branch_nodes.get(tid, {}).get("label", tid)
            tgt_name = sanitize_filename(tgt_label)
            lines.append(f"- {RELATION_EMOJI.get(rel, '->')} [[{tgt_name}|{tgt_label}]]")
        lines.append("")

    inc = incoming.get(nid, [])
    if inc:
        lines.append("## Connected From")
        lines.append("")
        for rel, sid in inc[:20]:
            src_label = branch_nodes.get(sid, {}).get("label", sid)
            src_name = sanitize_filename(src_label)
            lines.append(f"- {RELATION_EMOJI.get(rel, '<-')} [[{src_name}|{src_label}]]")
        lines.append("")

    (branch_dir / f"{filename}.md").write_text("\n".join(lines))
