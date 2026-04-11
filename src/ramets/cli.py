"""CLI entry point — `ramets` command.

Your codebase is one organism. Each branch is a ramet.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from ramets.core.branch import (
    current_branch,
    get_db_path,
    get_main_repo_root,
    get_ramets_dir,
)
from ramets.core.db import GenetDB


def _get_db() -> GenetDB:
    """Get a database connection, or exit with helpful message."""
    db_path = get_db_path()
    if not db_path.exists():
        click.echo("No ramets database found. Run `ramets init` first.", err=True)
        sys.exit(1)
    return GenetDB(db_path)


@click.group()
@click.version_option()
def main():
    """ramets — Per-branch AI coding context.

    Your codebase is one organism. Each branch is a ramet.

    Named after Pando (Populus tremuloides), the world's largest organism —
    individual trunks (ramets) sharing one root system (genet).
    """
    pass


@main.command()
@click.option("--no-hooks", is_flag=True, help="Skip git/Claude hook installation")
@click.option("--no-claude-hooks", is_flag=True, help="Skip Claude Code hook installation")
@click.option("--install-desktop", is_flag=True, help="Also configure Claude Desktop MCP server")
def init(no_hooks: bool, no_claude_hooks: bool, install_desktop: bool):
    """Initialize ramets in the current repository.

    Creates .ramets/, builds the genet (base graph), and installs hooks.
    """
    try:
        repo_root = get_main_repo_root()
    except RuntimeError:
        click.echo("Error: Not inside a git repository.", err=True)
        sys.exit(1)

    ramets_dir = get_ramets_dir()
    ramets_dir.mkdir(parents=True, exist_ok=True)

    # Initialize database
    db_path = ramets_dir / "store.db"
    db = GenetDB(db_path)
    db.init_schema()

    click.echo(f"Initialized .ramets/ at {ramets_dir}")

    # Build genet
    click.echo("Building genet (base graph)...")
    from ramets.core.base import build_genet

    graph_data = build_genet(db, repo_root)
    node_count = len(graph_data.get("nodes", []))
    edge_count = len(graph_data.get("links", []))
    click.echo(f"Genet built: {node_count} nodes, {edge_count} edges")

    # Register current branch
    branch = current_branch(cwd=repo_root)
    db.register_branch(branch)
    click.echo(f"Registered branch: {branch}")

    # Install git hooks
    if not no_hooks:
        from ramets.hooks.git import install_git_hooks

        installed = install_git_hooks(repo_root)
        click.echo(f"Installed git hooks: {', '.join(installed)}")

    # Install Claude Code hooks
    if not no_hooks and not no_claude_hooks:
        from ramets.hooks.claude import install_claude_hooks

        install_claude_hooks(repo_root)
        click.echo("Installed Claude Code hooks in .claude/settings.json")

    # Install Claude Code skill
    if not no_claude_hooks:
        _install_skill()

    # Configure Claude Desktop MCP server
    if install_desktop:
        from ramets.hooks.desktop import install_desktop_config, install_project_instruction

        config_path = install_desktop_config(repo_root)
        click.echo(f"Configured Claude Desktop MCP server in {config_path}")
        if install_project_instruction(repo_root):
            click.echo("Added session_summary instruction to CLAUDE.md")

    # Add .ramets/ to .gitignore
    gitignore = repo_root / ".gitignore"
    if gitignore.exists():
        content = gitignore.read_text()
        if ".ramets/" not in content:
            with open(gitignore, "a") as f:
                f.write("\n# ramets knowledge graph (local)\n.ramets/\n")
            click.echo("Added .ramets/ to .gitignore")
    else:
        gitignore.write_text("# ramets knowledge graph (local)\n.ramets/\n")
        click.echo("Created .gitignore with .ramets/")

    db.close()

    click.echo('\nReady! Try: ramets query "how does the main module work?"')
    click.echo(f"Storage: {db_path.stat().st_size / 1024:.0f} KB")


@main.command()
def build():
    """Full genet rebuild from current HEAD."""
    db = _get_db()
    repo_root = get_main_repo_root()

    click.echo("Rebuilding genet...")
    from ramets.core.base import build_genet

    graph_data = build_genet(db, repo_root)
    node_count = len(graph_data.get("nodes", []))
    edge_count = len(graph_data.get("links", []))
    click.echo(f"Genet rebuilt: {node_count} nodes, {edge_count} edges")

    db.close()


@main.command()
def update():
    """Incremental delta update for current branch.

    Called by post-commit hook. Computes what changed vs genet.
    """
    db = _get_db()
    repo_root = get_main_repo_root()
    branch = current_branch(cwd=repo_root)

    from ramets.core.base import load_genet_or_build
    from ramets.core.delta import compute_deltas
    from ramets.extract.ast_bridge import extract_graph

    genet = load_genet_or_build(db, repo_root)
    branch_graph = extract_graph(repo_root)
    deltas = compute_deltas(genet, branch_graph)

    from ramets.core.branch import current_commit

    commit = current_commit(cwd=repo_root)

    # Replace deltas (compute_deltas returns full diff vs genet, not incremental)
    db.conn.execute("DELETE FROM ramet_deltas WHERE branch = ?", (branch,))
    db.conn.execute("DELETE FROM ramets WHERE branch = ?", (branch,))
    db.conn.commit()

    if deltas:
        db.append_deltas(branch, commit, deltas)
        click.echo(f"{len(deltas)} deltas for {branch}")
    else:
        click.echo(f"No changes for {branch}")

    db.close()


@main.command()
def status():
    """Show genet freshness, ramet count, delta sizes, storage."""
    db = _get_db()

    genet_meta = db.genet_meta()
    if genet_meta:
        click.echo(
            f"Genet: {genet_meta['node_count']} nodes, "
            f"{genet_meta['edge_count']} edges "
            f"(commit {genet_meta['commit_sha']}, built {genet_meta['built_at']})"
        )
    else:
        click.echo("Genet: not built")

    branches = db.list_branches()
    click.echo(f"\nBranches: {len(branches)}")
    for b in branches:
        delta_count = db.delta_count(b["name"])
        ramet = db.ramet_meta(b["name"])
        cached = f" [cached: {ramet['node_count']}n/{ramet['edge_count']}e]" if ramet else ""
        click.echo(f"  {b['name']}: {delta_count} deltas{cached}")

    ramets_dir = get_ramets_dir()
    db_size = (ramets_dir / "store.db").stat().st_size
    click.echo(f"\nStorage: {db_size / 1024:.0f} KB ({ramets_dir})")

    db.close()


@main.command("query")
@click.argument("question")
@click.option("--branch", "-b", default=None, help="Branch to query (default: current)")
@click.option("--depth", "-d", default=3, help="BFS traversal depth")
@click.option("--budget", default=2000, help="Approximate token budget")
def query_cmd(question: str, branch: str | None, depth: int, budget: int):
    """Query the knowledge graph."""
    db = _get_db()

    from ramets.core.materialize import query_graph

    result = query_graph(db, question, branch=branch, depth=depth, token_budget=budget)
    click.echo(result)
    db.close()


@main.command("diff")
@click.argument("branch_a")
@click.argument("branch_b", default="main")
def diff_cmd(branch_a: str, branch_b: str):
    """Show graph differences between two branches."""
    db = _get_db()

    from ramets.core.materialize import diff_branches

    result = diff_branches(db, branch_a, branch_b)
    click.echo(result)
    db.close()


@main.command()
def summary():
    """Print the session summary (~400 tokens)."""
    db = _get_db()

    from ramets.core.materialize import summary as gen_summary

    result = gen_summary(db)
    click.echo(result)
    db.close()


@main.command()
@click.option("--open", "open_obsidian", is_flag=True, help="Open vault in Obsidian")
@click.option("--dir", "vault_dir", default=None, help="Custom output directory")
@click.option("--all-branches", is_flag=True, help="Generate all branch layers")
def obsidian(open_obsidian: bool, vault_dir: str | None, all_branches: bool):
    """Generate Obsidian vault with branch layers."""
    db = _get_db()

    from ramets.obsidian.vault import generate_vault

    output = Path(vault_dir) if vault_dir else get_ramets_dir() / "obsidian"

    branches_to_render = None
    if all_branches:
        branches_to_render = [b["name"] for b in db.list_branches()]

    generate_vault(db, output, branches=branches_to_render)
    click.echo(f"Obsidian vault generated at {output}")

    if open_obsidian:
        import subprocess

        subprocess.run(
            ["open", f"obsidian://open?path={output}"],
            check=False,
        )
        click.echo("Opening in Obsidian...")

    db.close()


@main.command()
@click.option("--question", "-q", required=True, help="The decision question")
@click.option(
    "--options",
    "-o",
    multiple=True,
    required=True,
    help="Options (repeat for each). Format: 'label' or 'label:description'",
)
@click.option("--chosen", "-c", type=int, required=True, help="Index of chosen option (0-based)")
@click.option(
    "--category",
    type=click.Choice(
        [
            "architecture",
            "implementation",
            "dependency",
            "naming",
            "algorithm",
            "refactor",
            "config",
            "test_strategy",
            "api_design",
            "data_model",
            "performance",
            "security",
        ]
    ),
    default="implementation",
    help="Decision category",
)
@click.option("--rationale", "-r", default="", help="Why this option was chosen")
@click.option("--confidence", type=float, default=0.8, help="Confidence level (0.0-1.0)")
@click.option("--file", "context_files", multiple=True, help="Related files")
def decide(
    question: str,
    options: tuple[str, ...],
    chosen: int,
    category: str,
    rationale: str,
    confidence: float,
    context_files: tuple[str, ...],
):
    """Record a design/implementation decision.

    Examples:
        ramets decide -q "Auth strategy?" -o "JWT" -o "Session cookies" -c 0 -r "Stateless"
        ramets decide -q "ORM choice?" -o "SQLAlchemy:Full ORM" -o "Raw SQL" -c 1 --category dependency
    """
    db = _get_db()

    from ramets.core.branch import current_commit
    from ramets.decision.schema import Decision, Option
    from ramets.decision.tracker import DecisionTracker

    if chosen < 0 or chosen >= len(options):
        click.echo(f"Error: --chosen must be 0-{len(options) - 1}", err=True)
        sys.exit(1)

    parsed_options = []
    for opt_str in options:
        if ":" in opt_str:
            label, desc = opt_str.split(":", 1)
            parsed_options.append(Option(label=label.strip(), description=desc.strip()))
        else:
            parsed_options.append(Option(label=opt_str.strip()))

    branch = current_branch()
    commit = current_commit()

    decision = Decision(
        branch=branch,
        category=category,
        question=question,
        options=parsed_options,
        chosen=chosen,
        rationale=rationale,
        confidence=confidence,
        context_files=list(context_files),
        commit_sha=commit,
    )

    tracker = DecisionTracker(db)
    did = tracker.record(decision)
    chosen_label = parsed_options[chosen].label

    click.echo(f"Decision recorded: {did}")
    click.echo(f"  Q: {question}")
    click.echo(f"  Chose: {chosen_label}")
    if rationale:
        click.echo(f"  Why: {rationale}")

    db.close()


@main.command()
@click.option("--branch", "-b", default=None, help="Filter by branch")
@click.option("--category", default=None, help="Filter by category")
@click.option("--status", default="active", help="Filter by status")
@click.option("--search", "-s", default=None, help="Full-text search")
@click.option("--id", "decision_id", default=None, help="Show specific decision by ID")
def decisions(
    branch: str | None,
    category: str | None,
    status: str,
    search: str | None,
    decision_id: str | None,
):
    """List or search decisions for the current branch.

    Examples:
        ramets decisions                     # All active decisions
        ramets decisions -s "auth"           # Search for auth-related
        ramets decisions --id abc123         # Show specific decision
        ramets decisions --category architecture
    """
    db = _get_db()

    from ramets.decision.tracker import DecisionTracker

    tracker = DecisionTracker(db)

    if decision_id:
        d = tracker.get(decision_id)
        if d is None:
            click.echo(f"Decision not found: {decision_id}", err=True)
            sys.exit(1)
        _print_decision_detail(d)
        db.close()
        return

    if search:
        results = tracker.search(search)
    else:
        if branch is None:
            branch = current_branch()
        results = tracker.query(branch=branch, category=category, status=status)

    if not results:
        click.echo("No decisions found.")
    else:
        click.echo(f"Decisions: {len(results)}")
        for d in results:
            chosen_label = d.options[d.chosen].label if d.options else "?"
            status_icon = {"active": "●", "superseded": "○", "reversed": "✗", "deferred": "◌"}.get(
                d.status.value, "?"
            )
            click.echo(f"  {status_icon} [{d.id}] {d.question}")
            click.echo(f"    → {chosen_label} ({d.category.value}, {d.confidence or '?'})")

    db.close()


def _print_decision_detail(d) -> None:
    """Print full decision details."""
    click.echo(f"Decision: {d.id}")
    click.echo(f"  Question: {d.question}")
    click.echo(f"  Category: {d.category.value}")
    click.echo(f"  Branch: {d.branch}")
    click.echo(f"  Status: {d.status.value}")
    click.echo(f"  Timestamp: {d.timestamp}")
    click.echo(f"  Confidence: {d.confidence}")
    if d.commit_sha:
        click.echo(f"  Commit: {d.commit_sha}")
    click.echo("  Options:")
    for i, opt in enumerate(d.options):
        marker = " ✓" if i == d.chosen else "  "
        desc = f" — {opt.description}" if opt.description else ""
        click.echo(f"   {marker} [{i}] {opt.label}{desc}")
        if opt.pros:
            for pro in opt.pros:
                click.echo(f"         + {pro}")
        if opt.cons:
            for con in opt.cons:
                click.echo(f"         - {con}")
    if d.rationale:
        click.echo(f"  Rationale: {d.rationale}")
    if d.context_files:
        click.echo(f"  Files: {', '.join(d.context_files)}")


@main.command("install-skill")
def install_skill_cmd():
    """Install the ramets Claude Code skill to ~/.claude/skills/."""
    _install_skill()


def _install_skill() -> None:
    """Install SKILL.md to ~/.claude/skills/ramets/ and register in CLAUDE.md."""
    import shutil

    home = Path.home()
    skill_dir = home / ".claude" / "skills" / "ramets"
    skill_dir.mkdir(parents=True, exist_ok=True)

    # Copy SKILL.md from the package
    pkg_skill = Path(__file__).parent / "skill" / "SKILL.md"
    if pkg_skill.exists():
        shutil.copy2(pkg_skill, skill_dir / "SKILL.md")
    else:
        click.echo("Warning: SKILL.md not found in package", err=True)
        return

    # Register in CLAUDE.md if not already there
    claude_md = home / ".claude" / "CLAUDE.md"
    registration = (
        "\n# ramets\n"
        "- **ramets** (`~/.claude/skills/ramets/SKILL.md`) - per-branch AI coding context "
        "with delta-encoded knowledge graphs, decision tracking, and Obsidian visualization. "
        "Trigger: `/ramets`\n"
        "When the user types `/ramets`, invoke the Skill tool with "
        '`skill: "ramets"` before doing anything else.\n'
    )

    if claude_md.exists():
        content = claude_md.read_text()
        if "skills/ramets" not in content:
            with open(claude_md, "a") as f:
                f.write(registration)
            click.echo("Registered /ramets skill in ~/.claude/CLAUDE.md")
        else:
            click.echo("Skill already registered in ~/.claude/CLAUDE.md")
    else:
        claude_md.parent.mkdir(parents=True, exist_ok=True)
        claude_md.write_text(registration)
        click.echo("Created ~/.claude/CLAUDE.md with /ramets skill")

    click.echo(f"Installed skill to {skill_dir / 'SKILL.md'}")


@main.command()
@click.option("--uninstall", is_flag=True, help="Remove ramets from Desktop config")
def desktop(uninstall: bool):
    """Configure Claude Desktop to use the ramets MCP server.

    Adds ramets as an MCP server in claude_desktop_config.json and
    writes a CLAUDE.md project instruction for automatic session_summary
    injection on conversation start.

    Examples:
        ramets desktop               # Install Desktop config
        ramets desktop --uninstall   # Remove Desktop config
    """
    repo_root = get_main_repo_root()

    if uninstall:
        from ramets.hooks.desktop import uninstall_desktop_config

        result = uninstall_desktop_config()
        if result:
            click.echo(f"Removed ramets from {result}")
        else:
            click.echo("No Desktop config to remove.")
        return

    from ramets.hooks.desktop import install_desktop_config, install_project_instruction

    config_path = install_desktop_config(repo_root)
    click.echo(f"Configured Claude Desktop MCP server in {config_path}")
    click.echo("  Server: ramets serve (stdio)")
    click.echo(f"  Working dir: {repo_root}")

    if install_project_instruction(repo_root):
        click.echo("Added session_summary instruction to CLAUDE.md")
    else:
        click.echo("CLAUDE.md already has session_summary instruction")

    click.echo("\nRestart Claude Desktop to pick up the new MCP server.")


@main.command()
def gc():
    """Prune dead ramets, compact the genet database."""
    db = _get_db()

    from ramets.core.branch import list_worktrees

    # Get active branches from worktrees + current
    active = {current_branch()}
    for wt in list_worktrees():
        if "branch" in wt:
            active.add(wt["branch"])

    # Find stale branches
    all_branches = db.list_branches()
    stale = [b for b in all_branches if b["name"] not in active]

    if stale:
        for b in stale:
            db.delete_ramet(b["name"])
            db.conn.execute("DELETE FROM branches WHERE name = ?", (b["name"],))
            click.echo(f"  Pruned: {b['name']}")
        db.conn.commit()
        click.echo(f"Pruned {len(stale)} stale ramets")
    else:
        click.echo("No stale ramets to prune")

    # VACUUM to reclaim space
    db.conn.execute("VACUUM")
    click.echo("Database compacted")

    db.close()


@main.command()
def serve():
    """Start MCP server (stdio for Claude Code)."""
    try:
        from ramets.mcp.server import run_server

        run_server()
    except ImportError:
        click.echo(
            "MCP dependencies not installed. Run: pip install ramets[mcp]",
            err=True,
        )
        sys.exit(1)


@main.command()
def rebase():
    """Recompute genet and all branch deltas after a git rebase.

    After rebasing, the merge-base changes and existing deltas may be
    invalid. This command rebuilds the genet from HEAD and recomputes
    deltas for every registered branch.
    """
    db = _get_db()
    repo_root = get_main_repo_root()

    # Step 1: Rebuild genet
    click.echo("Rebuilding genet from HEAD...")
    from ramets.core.base import build_genet

    graph_data = build_genet(db, repo_root)
    node_count = len(graph_data.get("nodes", []))
    edge_count = len(graph_data.get("links", []))
    click.echo(f"Genet rebuilt: {node_count} nodes, {edge_count} edges")

    # Step 2: Recompute deltas for all registered branches
    from ramets.core.branch import current_commit
    from ramets.core.delta import compute_deltas
    from ramets.extract.ast_bridge import extract_graph

    branches = db.list_branches()
    if not branches:
        click.echo("No branches registered.")
        db.close()
        return

    branch_graph = extract_graph(repo_root)
    commit = current_commit(cwd=repo_root)

    for b in branches:
        name = b["name"]
        # Clear old deltas and cached ramets
        db.conn.execute("DELETE FROM ramet_deltas WHERE branch = ?", (name,))
        db.conn.execute("DELETE FROM ramets WHERE branch = ?", (name,))
        db.conn.commit()

        deltas = compute_deltas(graph_data, branch_graph)
        if deltas:
            db.append_deltas(name, commit, deltas)
            click.echo(f"  {name}: {len(deltas)} deltas")
        else:
            click.echo(f"  {name}: no changes")

    click.echo(f"Recomputed deltas for {len(branches)} branches")
    db.close()


if __name__ == "__main__":
    main()
