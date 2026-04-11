"""Tests for commit message mining (decision/mining.py)."""

import pytest

from ramets.decision.mining import mine_commit
from ramets.decision.schema import DecisionCategory


class TestConventionalCommits:
    """Test mining from conventional commit messages."""

    def test_chose_over_pattern(self):
        """'chose X over Y' extracts a choice decision."""
        decisions = mine_commit(
            "feat: chose JWT over sessions for auth",
            branch="feat/auth",
            commit_sha="abc123",
            changed_files=["src/auth.py"],
        )
        assert len(decisions) == 1
        d = decisions[0]
        assert d.confidence == 0.9
        assert len(d.options) == 2
        assert d.options[0].label == "JWT"
        assert d.options[1].label == "sessions"
        assert d.chosen == 0
        assert d.category == DecisionCategory.implementation
        assert d.commit_sha == "abc123"

    def test_switch_from_to_pattern(self):
        """'switch from X to Y' extracts a switch decision."""
        decisions = mine_commit(
            "refactor: switched from unittest to pytest",
            branch="main",
            commit_sha="def456",
            changed_files=["tests/conftest.py"],
        )
        assert len(decisions) == 1
        d = decisions[0]
        assert d.confidence == 0.8
        assert d.chosen == 1  # new option is chosen
        assert d.options[0].label == "unittest"
        assert d.options[1].label == "pytest"
        assert d.category == DecisionCategory.refactor

    def test_replace_with_pattern(self):
        """'replace X with Y' extracts a switch decision."""
        decisions = mine_commit(
            "build: replaced webpack with vite",
            branch="main",
            commit_sha="ghi789",
            changed_files=["webpack.config.js", "vite.config.ts"],
        )
        assert len(decisions) == 1
        d = decisions[0]
        assert d.confidence == 0.8
        assert d.chosen == 1
        assert d.category == DecisionCategory.dependency

    def test_extract_pattern(self):
        """'extract X from Y' extracts an architecture decision."""
        decisions = mine_commit(
            "refactor: extracted auth middleware from server.py",
            branch="feat/auth",
            commit_sha="jkl012",
            changed_files=["src/auth.py", "src/server.py"],
        )
        assert len(decisions) == 1
        d = decisions[0]
        assert d.confidence == 0.7
        assert d.category == DecisionCategory.architecture

    def test_adopt_pattern(self):
        """'add/use X' extracts an adopt decision."""
        decisions = mine_commit(
            "feat: add pydantic for validation",
            branch="main",
            commit_sha="mno345",
            changed_files=["requirements.txt"],
        )
        assert len(decisions) == 1
        d = decisions[0]
        assert d.confidence == 0.6
        assert d.options[0].label == "pydantic"

    def test_prefix_category_mapping(self):
        """Commit prefixes map to correct categories."""
        for prefix, expected_cat in [
            ("feat", DecisionCategory.implementation),
            ("fix", DecisionCategory.implementation),
            ("perf", DecisionCategory.performance),
            ("build", DecisionCategory.dependency),
            ("test", DecisionCategory.test_strategy),
        ]:
            decisions = mine_commit(
                f"{prefix}: chose A over B",
                branch="main",
                commit_sha="abc",
                changed_files=[],
            )
            assert len(decisions) == 1
            assert decisions[0].category == expected_cat


class TestIgnoredPrefixes:
    """Test that certain prefixes are skipped."""

    @pytest.mark.parametrize("prefix", ["chore", "ci", "docs", "style"])
    def test_default_ignored_prefixes(self, prefix):
        """Default ignored prefixes produce no decisions."""
        decisions = mine_commit(
            f"{prefix}: update something",
            branch="main",
            commit_sha="abc",
            changed_files=[],
        )
        assert decisions == []

    def test_custom_ignore_prefixes(self):
        """Custom ignore list overrides defaults."""
        # 'feat' is normally not ignored; ignore it here
        decisions = mine_commit(
            "feat: chose A over B",
            branch="main",
            commit_sha="abc",
            changed_files=[],
            ignore_prefixes=["feat"],
        )
        assert decisions == []


class TestMergeCommits:
    """Test that merge commits are skipped."""

    def test_merge_branch(self):
        decisions = mine_commit(
            "Merge branch 'main' into feat/auth",
            branch="feat/auth",
            commit_sha="abc",
            changed_files=[],
        )
        assert decisions == []

    def test_merge_pull_request(self):
        decisions = mine_commit(
            "Merge pull request #42 from user/feat",
            branch="main",
            commit_sha="abc",
            changed_files=[],
        )
        assert decisions == []


class TestConfidenceThreshold:
    """Test min_confidence filtering."""

    def test_high_threshold_filters_low_confidence(self):
        """High threshold filters out lower-confidence patterns."""
        decisions = mine_commit(
            "feat: add pydantic for validation",
            branch="main",
            commit_sha="abc",
            changed_files=[],
            min_confidence=0.7,
        )
        assert decisions == []  # adopt pattern is 0.6

    def test_low_threshold_includes_more(self):
        """Low threshold includes lower-confidence results."""
        decisions = mine_commit(
            "feat: add pydantic for validation",
            branch="main",
            commit_sha="abc",
            changed_files=[],
            min_confidence=0.5,
        )
        assert len(decisions) == 1


class TestNonConventionalCommits:
    """Test fallback for non-conventional commit messages."""

    def test_pattern_match_without_prefix(self):
        """Patterns still work on non-conventional messages."""
        decisions = mine_commit(
            "Chose SQLAlchemy over raw SQL for database access",
            branch="main",
            commit_sha="abc",
            changed_files=["src/db.py"],
        )
        assert len(decisions) == 1
        assert decisions[0].confidence == 0.9

    def test_low_confidence_note(self):
        """Substantial non-matching messages become low-confidence notes."""
        decisions = mine_commit(
            "Fixed the authentication flow to handle edge cases properly",
            branch="main",
            commit_sha="abc",
            changed_files=["src/auth.py"],
            min_confidence=0.2,
        )
        assert len(decisions) == 1
        assert decisions[0].confidence == 0.2

    def test_short_messages_skipped(self):
        """Short non-conventional messages produce nothing."""
        decisions = mine_commit(
            "fix typo",
            branch="main",
            commit_sha="abc",
            changed_files=[],
            min_confidence=0.1,
        )
        assert decisions == []

    def test_empty_message(self):
        decisions = mine_commit("", branch="main", commit_sha="abc", changed_files=[])
        assert decisions == []


class TestContextFiles:
    """Test that changed files are passed through."""

    def test_files_limited_to_10(self):
        files = [f"src/file{i}.py" for i in range(20)]
        decisions = mine_commit(
            "feat: chose A over B",
            branch="main",
            commit_sha="abc",
            changed_files=files,
        )
        assert len(decisions[0].context_files) == 10
