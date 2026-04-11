"""Git hook generator and installer.

Installs post-commit, post-checkout, post-merge, and post-rewrite hooks
that keep the genet and ramets up to date. Zero LLM tokens — all local.
"""

from __future__ import annotations

import stat
from pathlib import Path
from textwrap import dedent

from ramets.core.branch import get_main_repo_root

# Fence comments to identify our hooks in shared hook files
FENCE_START = "# ramets-hook-start"
FENCE_END = "# ramets-hook-end"


def install_git_hooks(repo_path: Path | None = None) -> list[str]:
    """Install all git hooks. Returns list of installed hook names.

    Appends to existing hooks if present (using fence comments).
    """
    if repo_path is None:
        repo_path = get_main_repo_root()

    hooks_dir = repo_path / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    installed = []
    for name, content in _hook_contents().items():
        hook_path = hooks_dir / name
        _install_hook(hook_path, content)
        installed.append(name)

    return installed


def uninstall_git_hooks(repo_path: Path | None = None) -> list[str]:
    """Remove ramets hooks (between fence comments)."""
    if repo_path is None:
        repo_path = get_main_repo_root()

    hooks_dir = repo_path / ".git" / "hooks"
    removed = []

    for name in _hook_contents():
        hook_path = hooks_dir / name
        if hook_path.exists():
            content = hook_path.read_text()
            if FENCE_START in content:
                # Remove our fenced section
                lines = content.splitlines(keepends=True)
                new_lines = []
                in_fence = False
                for line in lines:
                    if FENCE_START in line:
                        in_fence = True
                        continue
                    if FENCE_END in line:
                        in_fence = False
                        continue
                    if not in_fence:
                        new_lines.append(line)

                remaining = "".join(new_lines).strip()
                if remaining and remaining != "#!/bin/bash":
                    hook_path.write_text(remaining + "\n")
                else:
                    hook_path.unlink()
                removed.append(name)

    return removed


def _install_hook(hook_path: Path, content: str) -> None:
    """Install a hook, appending to existing if present."""
    if hook_path.exists():
        existing = hook_path.read_text()
        # Remove old ramets hook if present
        if FENCE_START in existing:
            lines = existing.splitlines(keepends=True)
            new_lines = []
            in_fence = False
            for line in lines:
                if FENCE_START in line:
                    in_fence = True
                    continue
                if FENCE_END in line:
                    in_fence = False
                    continue
                if not in_fence:
                    new_lines.append(line)
            existing = "".join(new_lines)

        # Append our hook
        hook_path.write_text(existing.rstrip() + "\n\n" + content + "\n")
    else:
        hook_path.write_text("#!/bin/bash\n\n" + content + "\n")

    # Make executable
    hook_path.chmod(hook_path.stat().st_mode | stat.S_IEXEC)


def _find_ramets_python() -> str:
    """Find the Python interpreter that has ramets installed."""
    import sys

    return sys.executable


def _hook_contents() -> dict[str, str]:
    """Generate all hook scripts."""
    python = _find_ramets_python()

    post_commit = dedent(f"""\
        {FENCE_START}
        # Auto-update ramet delta after each commit.
        # Zero LLM tokens — all local AST extraction.
        REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
        if [ -f "$REPO_ROOT/.git" ]; then
            REPO_ROOT="$(sed 's|gitdir: ||;s|/\\.git/worktrees/.*||' "$REPO_ROOT/.git")"
        fi
        if [ -d "$REPO_ROOT/.ramets" ]; then
            "{python}" -c "
        from ramets.core.branch import get_main_repo_root, current_branch, current_commit
        from ramets.core.db import GenetDB
        from ramets.extract.ast_bridge import extract_graph
        from ramets.core.delta import compute_deltas
        from pathlib import Path
        import sys

        try:
            repo = get_main_repo_root()
            db = GenetDB(repo / '.ramets' / 'store.db')
            genet = db.load_genet()
            if genet is None:
                sys.exit(0)
            branch = current_branch()
            commit = current_commit()
            branch_graph = extract_graph(repo)
            deltas = compute_deltas(genet, branch_graph)
            # Replace deltas (compute_deltas gives full diff vs genet)
            db.conn.execute('DELETE FROM ramet_deltas WHERE branch = ?', (branch,))
            db.conn.execute('DELETE FROM ramets WHERE branch = ?', (branch,))
            db.conn.commit()
            if deltas:
                db.append_deltas(branch, commit, deltas)
                print(f'[ramets] {{len(deltas)}} deltas for {{branch}}')
            db.close()
        except Exception as e:
            print(f'[ramets] post-commit hook failed: {{e}}', file=sys.stderr)
        " 2>&1
        fi
        {FENCE_END}""")

    post_checkout = dedent(f"""\
        {FENCE_START}
        # Register branch on checkout, prep ramet.
        PREV_HEAD=$1
        NEW_HEAD=$2
        BRANCH_SWITCH=$3
        if [ "$BRANCH_SWITCH" != "1" ]; then
            exit 0
        fi
        REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
        if [ -f "$REPO_ROOT/.git" ]; then
            REPO_ROOT="$(sed 's|gitdir: ||;s|/\\.git/worktrees/.*||' "$REPO_ROOT/.git")"
        fi
        if [ -d "$REPO_ROOT/.ramets" ]; then
            "{python}" -c "
        from ramets.core.branch import get_main_repo_root, current_branch
        from ramets.core.db import GenetDB
        try:
            repo = get_main_repo_root()
            db = GenetDB(repo / '.ramets' / 'store.db')
            branch = current_branch()
            db.register_branch(branch)
            db.close()
            print(f'[ramets] Registered branch: {{branch}}')
        except Exception as e:
            print(f'[ramets] post-checkout hook failed: {{e}}')
        " 2>&1
        fi
        {FENCE_END}""")

    post_merge = dedent(f"""\
        {FENCE_START}
        # After merge/pull, check if genet needs recomputation.
        REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
        if [ -f "$REPO_ROOT/.git" ]; then
            REPO_ROOT="$(sed 's|gitdir: ||;s|/\\.git/worktrees/.*||' "$REPO_ROOT/.git")"
        fi
        if [ -d "$REPO_ROOT/.ramets" ]; then
            "{python}" -c "
        from ramets.core.branch import get_main_repo_root, current_branch, current_commit
        from ramets.core.db import GenetDB
        from ramets.extract.ast_bridge import extract_graph
        from ramets.core.delta import compute_deltas
        try:
            repo = get_main_repo_root()
            db = GenetDB(repo / '.ramets' / 'store.db')
            branch = current_branch()
            commit = current_commit()
            genet = db.load_genet()
            if genet is None:
                sys.exit(0)
            branch_graph = extract_graph(repo)
            deltas = compute_deltas(genet, branch_graph)
            # Replace deltas (compute_deltas gives full diff vs genet)
            db.conn.execute('DELETE FROM ramet_deltas WHERE branch = ?', (branch,))
            db.conn.execute('DELETE FROM ramets WHERE branch = ?', (branch,))
            db.conn.commit()
            if deltas:
                db.append_deltas(branch, commit, deltas)
                print(f'[ramets] post-merge: {{len(deltas)}} deltas for {{branch}}')
            db.close()
        except Exception as e:
            print(f'[ramets] post-merge hook failed: {{e}}')
        " 2>&1
        fi
        {FENCE_END}""")

    post_rewrite = dedent(f"""\
        {FENCE_START}
        # After rebase/amend, rebuild deltas for rewritten commits.
        REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
        if [ -f "$REPO_ROOT/.git" ]; then
            REPO_ROOT="$(sed 's|gitdir: ||;s|/\\.git/worktrees/.*||' "$REPO_ROOT/.git")"
        fi
        if [ -d "$REPO_ROOT/.ramets" ]; then
            "{python}" -c "
        from ramets.core.branch import get_main_repo_root, current_branch, current_commit
        from ramets.core.db import GenetDB
        from ramets.extract.ast_bridge import extract_graph
        from ramets.core.delta import compute_deltas
        try:
            repo = get_main_repo_root()
            db = GenetDB(repo / '.ramets' / 'store.db')
            branch = current_branch()
            # Clear old deltas for this branch and recompute
            db.conn.execute('DELETE FROM ramet_deltas WHERE branch = ?', (branch,))
            db.conn.execute('DELETE FROM ramets WHERE branch = ?', (branch,))
            db.conn.commit()
            genet = db.load_genet()
            if genet:
                branch_graph = extract_graph(repo)
                deltas = compute_deltas(genet, branch_graph)
                if deltas:
                    commit = current_commit()
                    db.append_deltas(branch, commit, deltas)
                    print(f'[ramets] post-rewrite: {{len(deltas)}} deltas for {{branch}}')
            db.close()
        except Exception as e:
            print(f'[ramets] post-rewrite hook failed: {{e}}')
        " 2>&1
        fi
        {FENCE_END}""")

    return {
        "post-commit": post_commit,
        "post-checkout": post_checkout,
        "post-merge": post_merge,
        "post-rewrite": post_rewrite,
    }
