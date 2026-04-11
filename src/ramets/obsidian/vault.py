"""Obsidian vault generator — converts genet + ramets into navigable markdown.

Evolved from RODGR's graphify-to-obsidian.py. Adds branch layers, decision
notes, and 3D graph plugin configuration.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from ramets.core.branch import current_branch
from ramets.core.db import GenetDB
from ramets.core.materialize import materialize

RELATION_EMOJI = {
    "contains": "📦",
    "calls": "📞",
    "uses": "🔧",
    "imports": "📥",
    "imports_from": "📥",
    "inherits": "🧬",
    "method": "⚙️",
    "rationale_for": "💡",
}

COMMUNITY_COLORS = [
    "#e6194b",
    "#3cb44b",
    "#ffe119",
    "#4363d8",
    "#f58231",
    "#911eb4",
    "#42d4f4",
    "#f032e6",
    "#bfef45",
    "#fabed4",
    "#469990",
    "#dcbeff",
    "#9A6324",
    "#fffac8",
    "#800000",
    "#aaffc3",
    "#808000",
    "#ffd8b1",
    "#000075",
    "#a9a9a9",
]


def sanitize_filename(label: str) -> str:
    """Make a label safe for use as a filename."""
    name = re.sub(r'[<>:"/\\|?*]', "_", label)
    name = name.strip(". ")
    if len(name) > 80:
        name = name[:77] + "..."
    return name or "unnamed"


def generate_vault(
    db: GenetDB,
    vault_dir: Path,
    branches: list[str] | None = None,
    include_decisions: bool = True,
) -> None:
    """Generate an Obsidian vault from the genet + ramet data.

    Args:
        db: The genet database.
        vault_dir: Output directory for the vault.
        branches: Specific branches to render. None = current branch only.
        include_decisions: Whether to include decision notes.
    """
    vault_dir.mkdir(parents=True, exist_ok=True)

    # Get current branch graph
    branch = current_branch()
    graph_data = materialize(db, branch)
    nodes = graph_data.get("nodes", [])
    links = graph_data.get("links", [])

    node_by_id = {n["id"]: n for n in nodes}

    # Build adjacency
    outgoing: defaultdict[str, list[tuple[str, str]]] = defaultdict(list)
    incoming: defaultdict[str, list[tuple[str, str]]] = defaultdict(list)
    for link in links:
        src = link.get("source", "")
        tgt = link.get("target", "")
        rel = link.get("relation", "unknown")
        if src in node_by_id and tgt in node_by_id:
            outgoing[src].append((rel, tgt))
            incoming[tgt].append((rel, src))

    # Community grouping
    communities: defaultdict[int, list[dict]] = defaultdict(list)
    for n in nodes:
        communities[n.get("community", -1)].append(n)

    # ID to filename mapping
    id_to_filename = {n["id"]: sanitize_filename(n["label"]) for n in nodes}

    # Create base layer folders
    base_dir = vault_dir / "base"
    for cid in sorted(communities.keys()):
        (base_dir / f"C{cid:02d}").mkdir(parents=True, exist_ok=True)

    # Write node notes
    for n in nodes:
        nid = n["id"]
        label = n["label"]
        filename = id_to_filename[nid]
        community = n.get("community", -1)
        file_type = n.get("file_type", "")
        source_file = n.get("source_file", "")
        source_loc = n.get("source_location", "")

        lines = []

        # YAML frontmatter
        lines.append("---")
        lines.append(f"id: {nid}")
        lines.append(f"type: {file_type}")
        lines.append(f"community: {community}")
        if source_file:
            lines.append(f"source: {source_file}")
        tags = [f"community/C{community:02d}", f"type/{file_type or 'unknown'}", "layer/base"]
        lines.append(f"tags: [{', '.join(tags)}]")
        lines.append("---")
        lines.append("")
        lines.append(f"# {label}")
        lines.append("")

        if source_file:
            lines.append(f"**Source:** `{source_file}`{f' ({source_loc})' if source_loc else ''}")
            lines.append("")

        # Outgoing links
        out = outgoing.get(nid, [])
        if out:
            lines.append("## Connects To")
            lines.append("")
            by_rel: defaultdict[str, list[str]] = defaultdict(list)
            for rel, tid in out:
                by_rel[rel].append(tid)
            for rel, targets in sorted(by_rel.items()):
                emoji = RELATION_EMOJI.get(rel, "->")
                lines.append(f"### {emoji} {rel}")
                for tid in targets:
                    tgt_name = id_to_filename.get(tid, tid)
                    tgt_label = node_by_id[tid]["label"] if tid in node_by_id else tid
                    lines.append(f"- [[{tgt_name}|{tgt_label}]]")
                lines.append("")

        # Incoming links
        inc = incoming.get(nid, [])
        if inc:
            lines.append("## Connected From")
            lines.append("")
            by_rel_in: defaultdict[str, list[str]] = defaultdict(list)
            for rel, sid in inc:
                by_rel_in[rel].append(sid)
            for rel, sources in sorted(by_rel_in.items()):
                emoji = RELATION_EMOJI.get(rel, "<-")
                lines.append(f"### {emoji} {rel}")
                for sid in sources:
                    src_name = id_to_filename.get(sid, sid)
                    src_label = node_by_id[sid]["label"] if sid in node_by_id else sid
                    lines.append(f"- [[{src_name}|{src_label}]]")
                lines.append("")

        degree = len(out) + len(inc)
        lines.append("---")
        lines.append(f"*Degree: {degree} ({len(out)} out, {len(inc)} in)*")

        filepath = base_dir / f"C{community:02d}" / f"{filename}.md"
        filepath.write_text("\n".join(lines))

    # Write branch delta layers
    branches_to_render = branches or [branch]
    genet = db.load_genet()
    branch_note_count = 0
    if genet:
        from ramets.obsidian.layers import render_branch_layers

        branch_note_count = render_branch_layers(db, vault_dir, branches_to_render, genet)

    # Write decision notes
    decision_count = 0
    if include_decisions:
        decision_count = _write_decision_notes(db, vault_dir, branches_to_render)

    # Write index / MOC
    _write_index(vault_dir, nodes, links, communities, id_to_filename, node_by_id, branch)

    # Write Obsidian graph settings (2D built-in + 3D plugin)
    _write_graph_settings(vault_dir, communities)

    from ramets.obsidian.config import generate_3d_config

    generate_3d_config(vault_dir, communities, branches=branches_to_render)

    node_count = len(nodes)
    print(
        f"Wrote {node_count} base notes"
        f"{f', {branch_note_count} branch delta notes' if branch_note_count else ''}"
        f"{f', {decision_count} decision notes' if decision_count else ''}"
        f" to {vault_dir}"
    )


def _write_decision_notes(
    db: GenetDB,
    vault_dir: Path,
    branches: list[str],
) -> int:
    """Write decision notes as Obsidian markdown.

    Returns the number of decisions written.
    """
    from ramets.decision.tracker import DecisionTracker

    tracker = DecisionTracker(db)
    decisions_dir = vault_dir / "decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for branch in branches:
        decisions = tracker.for_branch(branch)
        for d in decisions:
            lines = [
                "---",
                f"id: {d.id}",
                f"branch: {d.branch}",
                f"category: {d.category.value}",
                f"status: {d.status.value}",
                f"confidence: {d.confidence or 'unknown'}",
                f"tags: [decision, decision/{d.category.value}, layer/decision]",
                "---",
                "",
                f"# {'💡' if d.status.value == 'active' else '👻'} {d.question}",
                "",
                f"**Category:** {d.category.value} | "
                f"**Branch:** `{d.branch}` | "
                f"**Confidence:** {d.confidence or '?'}",
                "",
                "## Options",
                "",
            ]

            for i, opt in enumerate(d.options):
                marker = "**[CHOSEN]**" if i == d.chosen else ""
                desc = f" — {opt.description}" if opt.description else ""
                lines.append(f"### {i + 1}. {opt.label} {marker}")
                lines.append(f"{desc}")
                if opt.pros:
                    for pro in opt.pros:
                        lines.append(f"- ✅ {pro}")
                if opt.cons:
                    for con in opt.cons:
                        lines.append(f"- ❌ {con}")
                if opt.estimated_effort:
                    lines.append(f"- ⏱️ Effort: {opt.estimated_effort}")
                lines.append("")

            if d.rationale:
                lines.append("## Rationale")
                lines.append("")
                lines.append(d.rationale)
                lines.append("")

            if d.context_files:
                lines.append("## Related Files")
                lines.append("")
                for f in d.context_files:
                    lines.append(f"- `{f}`")
                lines.append("")

            if d.commit_sha:
                lines.append(f"*Commit: {d.commit_sha}*")

            filepath = decisions_dir / f"dec_{d.id}.md"
            filepath.write_text("\n".join(lines))
            count += 1

    return count


def _write_index(
    vault_dir: Path,
    nodes: list[dict],
    links: list[dict],
    communities: dict,
    id_to_filename: dict,
    node_by_id: dict,
    branch: str,
) -> None:
    """Write the Map of Content index note."""
    degree_map: defaultdict[str, int] = defaultdict(int)
    for link in links:
        degree_map[link.get("source", "")] += 1
        degree_map[link.get("target", "")] += 1

    lines = [
        "# ramets Knowledge Graph",
        "",
        f"**{len(nodes)} nodes** | **{len(links)} edges** | "
        f"**{len(communities)} communities** | Branch: `{branch}`",
        "",
        "Open **Graph View** (Cmd+G) to explore visually.",
        "",
        "## Most Connected (God Nodes)",
        "",
    ]

    top_nodes = sorted(degree_map.items(), key=lambda x: -x[1])[:15]
    for nid, deg in top_nodes:
        if nid in id_to_filename:
            name = id_to_filename[nid]
            label = node_by_id[nid]["label"]
            lines.append(f"- [[{name}|{label}]] -- {deg} connections")

    lines.extend(["", "## Communities", ""])

    for cid in sorted(communities.keys()):
        members = communities[cid]
        top_members = sorted(members, key=lambda n: degree_map.get(n["id"], 0), reverse=True)[:3]
        member_links = ", ".join(
            f"[[{id_to_filename[m['id']]}|{m['label'][:30]}]]" for m in top_members
        )
        lines.append(f"- **C{cid:02d}** ({len(members)} nodes): {member_links}")

    lines.extend(
        [
            "",
            "## Tips",
            "",
            "- **Graph View** (Cmd+G): See all connections visually",
            "- **Local Graph**: Click any note, toggle local graph in right sidebar",
            "- **Filter**: Use `tag:community/C00` or `tag:type/code` in search",
        ]
    )

    (vault_dir / "Index.md").write_text("\n".join(lines))


def _write_graph_settings(vault_dir: Path, communities: dict) -> None:
    """Write .obsidian/graph.json with community coloring."""
    obsidian_dir = vault_dir / ".obsidian"
    obsidian_dir.mkdir(exist_ok=True)

    color_groups = []
    for i, cid in enumerate(sorted(communities.keys())[:20]):
        color = COMMUNITY_COLORS[i % len(COMMUNITY_COLORS)]
        color_groups.append(
            {
                "query": f"tag:community/C{cid:02d}",
                "color": {"a": 1, "rgb": int(color.lstrip("#"), 16)},
            }
        )

    graph_settings = {
        "collapse-filter": False,
        "showTags": False,
        "showAttachments": False,
        "showOrphans": True,
        "colorGroups": color_groups,
        "showArrow": True,
        "nodeSizeMultiplier": 1.2,
        "lineSizeMultiplier": 1,
        "centerStrength": 0.5,
        "repelStrength": 10,
        "linkStrength": 1,
        "linkDistance": 250,
    }

    (obsidian_dir / "graph.json").write_text(json.dumps(graph_settings, indent=2))
    (obsidian_dir / "app.json").write_text(
        json.dumps(
            {
                "showLineNumber": True,
                "showFrontmatter": False,
            },
            indent=2,
        )
    )
