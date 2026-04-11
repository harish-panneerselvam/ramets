"""Branch and worktree detection.

Resolves the current branch, the main repo root (even from worktrees),
and the .ramets/ data directory.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def git_run(*args: str, cwd: Path | None = None) -> str:
    """Run a git command and return stdout, stripped."""
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
    )
    return result.stdout.strip()


def get_repo_root(cwd: Path | None = None) -> Path:
    """Get the working tree root (could be a worktree)."""
    root = git_run("rev-parse", "--show-toplevel", cwd=cwd)
    if not root:
        raise RuntimeError("Not inside a git repository")
    return Path(root)


def get_main_repo_root(cwd: Path | None = None) -> Path:
    """Get the main repo root, resolving through worktrees.

    In a worktree, .git is a file pointing to the main repo's .git/worktrees/<name>.
    We resolve back to the main repo root.
    """
    root = get_repo_root(cwd)
    git_common = git_run("rev-parse", "--git-common-dir", cwd=root)
    if git_common and not git_common.startswith("--"):
        common_path = Path(git_common)
        if not common_path.is_absolute():
            common_path = (root / common_path).resolve()
        # .git/worktrees/xxx → .git → repo root
        if common_path.name == ".git":
            return common_path.parent
        # Already at .git
        return common_path.parent
    return root


def get_ramets_dir(cwd: Path | None = None) -> Path:
    """Get the .ramets/ directory path (at main repo root)."""
    return get_main_repo_root(cwd) / ".ramets"


def get_db_path(cwd: Path | None = None) -> Path:
    """Get the path to store.db."""
    return get_ramets_dir(cwd) / "store.db"


def current_branch(cwd: Path | None = None) -> str:
    """Get the current branch name."""
    branch = git_run("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd)
    return branch or "HEAD"


def current_commit(cwd: Path | None = None) -> str:
    """Get the current commit SHA (short)."""
    return git_run("rev-parse", "--short", "HEAD", cwd=cwd)


def merge_base(branch_a: str = "HEAD", branch_b: str = "main",
               cwd: Path | None = None) -> str | None:
    """Find the merge-base commit between two branches."""
    result = git_run("merge-base", branch_a, branch_b, cwd=cwd)
    return result or None


def changed_files(since: str = "HEAD~1", until: str = "HEAD",
                  cwd: Path | None = None) -> list[str]:
    """Get files changed between two commits."""
    output = git_run("diff", "--name-only", since, until, cwd=cwd)
    if not output:
        return []
    return [f.strip() for f in output.splitlines() if f.strip()]


def is_worktree(cwd: Path | None = None) -> bool:
    """Check if the current directory is a git worktree (not the main repo)."""
    root = get_repo_root(cwd)
    main_root = get_main_repo_root(cwd)
    return root != main_root


def list_worktrees(cwd: Path | None = None) -> list[dict]:
    """List all worktrees for this repo."""
    output = git_run("worktree", "list", "--porcelain", cwd=cwd)
    if not output:
        return []
    worktrees = []
    current: dict = {}
    for line in output.splitlines():
        if line.startswith("worktree "):
            if current:
                worktrees.append(current)
            current = {"path": line.split(" ", 1)[1]}
        elif line.startswith("HEAD "):
            current["head"] = line.split(" ", 1)[1]
        elif line.startswith("branch "):
            current["branch"] = line.split(" ", 1)[1].replace("refs/heads/", "")
        elif line == "bare":
            current["bare"] = True
    if current:
        worktrees.append(current)
    return worktrees
