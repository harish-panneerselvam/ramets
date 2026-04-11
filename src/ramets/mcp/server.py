"""MCP server for ramets — 15 tools for Claude Code, Cursor, Codex.

Install with: pip install ramets[mcp]
Run with: ramets serve
Connect: claude mcp add ramets -- ramets serve
"""

from __future__ import annotations


def run_server():
    """Start the MCP server (stdio transport)."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        raise ImportError(
            "MCP dependencies not installed. Run: pip install ramets[mcp]"
        )

    mcp = FastMCP("ramets")

    # ── Code graph tools (7) ───────────────────────────────────────

    @mcp.tool()
    def query_graph(question: str, branch: str = "", depth: int = 3,
                    token_budget: int = 2000) -> str:
        """Search the knowledge graph for the current (or specified) branch."""
        from ramets.core.branch import get_db_path
        from ramets.core.db import GenetDB
        from ramets.core.materialize import query_graph as _query

        db = GenetDB(get_db_path())
        result = _query(db, question, branch=branch or None, depth=depth,
                        token_budget=token_budget)
        db.close()
        return result

    @mcp.tool()
    def get_node(label: str, branch: str = "") -> str:
        """Get full details for a node including connections."""
        from ramets.core.branch import get_db_path
        from ramets.core.db import GenetDB
        from ramets.core.materialize import materialize, to_networkx

        db = GenetDB(get_db_path())
        graph = materialize(db, branch or None)
        G = to_networkx(graph)
        db.close()

        # Find node by label
        for nid, data in G.nodes(data=True):
            if label.lower() in data.get("label", "").lower():
                edges_out = [(d.get("relation", "->"), G.nodes.get(t, {}).get("label", t))
                             for _, t, d in G.out_edges(nid, data=True)]
                edges_in = [(d.get("relation", "<-"), G.nodes.get(s, {}).get("label", s))
                            for s, _, d in G.in_edges(nid, data=True)]
                return (
                    f"Node: {data.get('label', nid)}\n"
                    f"Source: {data.get('source_file', '?')}\n"
                    f"Community: {data.get('community', '?')}\n"
                    f"Out: {edges_out[:10]}\n"
                    f"In: {edges_in[:10]}"
                )
        return f"No node matching '{label}'"

    @mcp.tool()
    def diff_branches(branch_a: str, branch_b: str = "main") -> str:
        """Show graph differences between two branches."""
        from ramets.core.branch import get_db_path
        from ramets.core.db import GenetDB
        from ramets.core.materialize import diff_branches as _diff

        db = GenetDB(get_db_path())
        result = _diff(db, branch_a, branch_b)
        db.close()
        return result

    @mcp.tool()
    def branch_status() -> str:
        """List all tracked branches with delta counts and storage."""
        from ramets.core.branch import get_db_path
        from ramets.core.db import GenetDB

        db = GenetDB(get_db_path())
        branches = db.list_branches()
        lines = [f"Branches: {len(branches)}"]
        for b in branches:
            dc = db.delta_count(b["name"])
            lines.append(f"  {b['name']}: {dc} deltas")
        db.close()
        return "\n".join(lines)

    @mcp.tool()
    def session_summary() -> str:
        """Get branch-aware summary for session start (~400 tokens)."""
        from ramets.core.branch import get_db_path
        from ramets.core.db import GenetDB
        from ramets.core.materialize import summary

        db = GenetDB(get_db_path())
        result = summary(db)
        db.close()
        return result

    # ── Decision tools (5) ─────────────────────────────────────────

    @mcp.tool()
    def record_decision(question: str, options: list[dict], chosen: int,
                        category: str = "implementation", rationale: str = "",
                        context_files: list[str] = [],
                        confidence: float = 0.8) -> str:
        """Record a design/implementation decision."""
        from ramets.core.branch import current_branch, get_db_path
        from ramets.core.db import GenetDB
        from ramets.decision.schema import Decision, Option
        from ramets.decision.tracker import DecisionTracker

        db = GenetDB(get_db_path())
        tracker = DecisionTracker(db)
        opts = [Option(**o) for o in options]
        decision = Decision(
            branch=current_branch(),
            category=category,
            question=question,
            options=opts,
            chosen=chosen,
            rationale=rationale,
            confidence=confidence,
            context_files=context_files,
        )
        did = tracker.record(decision)
        db.close()
        return f"Decision recorded: {did}"

    @mcp.tool()
    def list_decisions(branch: str = "", category: str = "",
                       status: str = "active") -> str:
        """List decisions filtered by branch/category/status."""
        from ramets.core.branch import get_db_path
        from ramets.core.db import GenetDB
        from ramets.decision.tracker import DecisionTracker

        db = GenetDB(get_db_path())
        tracker = DecisionTracker(db)
        decisions = tracker.query(branch=branch or None, category=category or None,
                                  status=status)
        db.close()
        lines = [f"Decisions: {len(decisions)}"]
        for d in decisions[:20]:
            lines.append(f"  [{d.id}] {d.question} -> {d.chosen_option.label} ({d.status.value})")
        return "\n".join(lines)

    @mcp.tool()
    def search_decisions(query: str) -> str:
        """Full-text search across decisions."""
        from ramets.core.branch import get_db_path
        from ramets.core.db import GenetDB
        from ramets.decision.tracker import DecisionTracker

        db = GenetDB(get_db_path())
        tracker = DecisionTracker(db)
        results = tracker.search(query)
        db.close()
        lines = [f"Search results for '{query}': {len(results)}"]
        for d in results[:10]:
            lines.append(f"  [{d.id}] {d.question} -> {d.chosen_option.label}")
        return "\n".join(lines)

    @mcp.tool()
    def get_decision(decision_id: str) -> str:
        """Get full decision details."""
        from ramets.core.branch import get_db_path
        from ramets.core.db import GenetDB
        from ramets.decision.tracker import DecisionTracker

        db = GenetDB(get_db_path())
        tracker = DecisionTracker(db)
        d = tracker.get(decision_id)
        db.close()
        if d is None:
            return f"Decision not found: {decision_id}"
        options_text = "\n".join(
            f"  {'[X]' if i == d.chosen else '[ ]'} {o.label}: {o.description}"
            for i, o in enumerate(d.options)
        )
        return (
            f"Decision: {d.question}\n"
            f"Category: {d.category.value}\n"
            f"Branch: {d.branch}\n"
            f"Status: {d.status.value}\n"
            f"Options:\n{options_text}\n"
            f"Rationale: {d.rationale}\n"
            f"Confidence: {d.confidence}\n"
            f"Files: {d.context_files}"
        )

    @mcp.tool()
    def supersede_decision(old_id: str, new_question: str, new_options: list[dict],
                           new_chosen: int, rationale: str = "") -> str:
        """Create a new decision that supersedes an existing one."""
        from ramets.core.branch import current_branch, get_db_path
        from ramets.core.db import GenetDB
        from ramets.decision.schema import Decision, Option
        from ramets.decision.tracker import DecisionTracker

        db = GenetDB(get_db_path())
        tracker = DecisionTracker(db)
        opts = [Option(**o) for o in new_options]
        new_dec = Decision(
            branch=current_branch(),
            category="implementation",
            question=new_question,
            options=opts,
            chosen=new_chosen,
            rationale=rationale,
        )
        new_id = tracker.supersede(old_id, new_dec)
        db.close()
        return f"Decision {old_id} superseded by {new_id}"

    # ── Obsidian tools (2) ─────────────────────────────────────────

    @mcp.tool()
    def generate_obsidian_vault(branches: list[str] = [],
                                include_decisions: bool = True) -> str:
        """Generate/update the Obsidian vault."""
        from ramets.core.branch import get_db_path, get_ramets_dir
        from ramets.core.db import GenetDB
        from ramets.obsidian.vault import generate_vault

        db = GenetDB(get_db_path())
        vault_dir = get_ramets_dir() / "obsidian"
        generate_vault(db, vault_dir, branches=branches or None,
                       include_decisions=include_decisions)
        db.close()
        return f"Vault generated at {vault_dir}"

    @mcp.tool()
    def obsidian_status() -> str:
        """Check Obsidian vault status."""
        from ramets.core.branch import get_ramets_dir

        vault_dir = get_ramets_dir() / "obsidian"
        if vault_dir.exists():
            note_count = len(list(vault_dir.rglob("*.md")))
            return f"Vault exists at {vault_dir} ({note_count} notes)"
        return "No Obsidian vault. Run `ramets obsidian` to generate."

    mcp.run(transport="stdio")
