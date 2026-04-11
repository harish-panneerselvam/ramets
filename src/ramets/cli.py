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
def init(no_hooks: bool, no_claude_hooks: bool):
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

    click.echo("\nReady! Try: ramets query \"how does the main module work?\"")
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

    if deltas:
        from ramets.core.branch import current_commit

        commit = current_commit(cwd=repo_root)
        db.append_deltas(branch, commit, deltas)
        # Invalidate cached ramet
        db.conn.execute("DELETE FROM ramets WHERE branch = ?", (branch,))
        db.conn.commit()
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
        click.echo(f"Genet: {genet_meta['node_count']} nodes, "
                    f"{genet_meta['edge_count']} edges "
                    f"(commit {genet_meta['commit_sha']}, built {genet_meta['built_at']})")
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
            click.echo(f"  Pruned: {b['name']}")
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


if __name__ == "__main__":
    main()
