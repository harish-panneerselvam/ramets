"""Tests for hook generation (hooks/git.py, hooks/claude.py)."""

import stat

import pytest

from ramets.hooks.git import (
    FENCE_END,
    FENCE_START,
    _hook_contents,
    install_git_hooks,
    uninstall_git_hooks,
)


@pytest.fixture
def fake_repo(tmp_path):
    """Create a minimal git repo structure."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir()
    return tmp_path


class TestGitHooks:
    def test_hook_contents_all_present(self):
        """All four hooks are generated."""
        hooks = _hook_contents()
        assert set(hooks.keys()) == {
            "post-commit",
            "post-checkout",
            "post-merge",
            "post-rewrite",
        }

    def test_hooks_have_fences(self):
        """Every hook has start and end fences."""
        hooks = _hook_contents()
        for name, content in hooks.items():
            assert FENCE_START in content, f"{name} missing start fence"
            assert FENCE_END in content, f"{name} missing end fence"

    def test_hooks_call_ramets(self):
        """Every hook calls ramets Python API."""
        hooks = _hook_contents()
        for name, content in hooks.items():
            assert "ramets" in content, f"{name} doesn't reference ramets"

    def test_post_commit_replaces_deltas(self):
        """Post-commit hook clears old deltas before appending."""
        hooks = _hook_contents()
        content = hooks["post-commit"]
        assert "DELETE FROM ramet_deltas" in content

    def test_post_rewrite_clears_deltas(self):
        """Post-rewrite hook clears deltas before recomputing."""
        hooks = _hook_contents()
        content = hooks["post-rewrite"]
        assert "DELETE FROM ramet_deltas" in content

    def test_install_creates_hooks(self, fake_repo):
        """install_git_hooks creates executable hook files."""
        installed = install_git_hooks(fake_repo)
        assert len(installed) == 4

        for name in installed:
            hook_path = fake_repo / ".git" / "hooks" / name
            assert hook_path.exists()
            assert hook_path.stat().st_mode & stat.S_IEXEC  # executable

    def test_install_preserves_existing(self, fake_repo):
        """Installing doesn't clobber existing hook content."""
        hook_path = fake_repo / ".git" / "hooks" / "post-commit"
        hook_path.write_text("#!/bin/bash\necho 'existing hook'\n")

        install_git_hooks(fake_repo)

        content = hook_path.read_text()
        assert "existing hook" in content
        assert FENCE_START in content

    def test_install_idempotent(self, fake_repo):
        """Installing twice doesn't duplicate fenced sections."""
        install_git_hooks(fake_repo)
        install_git_hooks(fake_repo)

        content = (fake_repo / ".git" / "hooks" / "post-commit").read_text()
        assert content.count(FENCE_START) == 1

    def test_uninstall_removes_fenced(self, fake_repo):
        """Uninstall removes ramets hook but preserves other content."""
        hook_path = fake_repo / ".git" / "hooks" / "post-commit"
        hook_path.write_text("#!/bin/bash\necho 'keep me'\n")

        install_git_hooks(fake_repo)
        removed = uninstall_git_hooks(fake_repo)

        assert "post-commit" in removed
        content = hook_path.read_text()
        assert "keep me" in content
        assert FENCE_START not in content

    def test_uninstall_removes_empty_hook(self, fake_repo):
        """Uninstall removes hook file if nothing else remains."""
        install_git_hooks(fake_repo)
        uninstall_git_hooks(fake_repo)

        # Hook files should be removed since they only had our content
        assert not (fake_repo / ".git" / "hooks" / "post-commit").exists()
