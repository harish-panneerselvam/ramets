"""Tests for decision deduplication (tracker.has_similar_decision)."""

import pytest

from ramets.core.db import GenetDB
from ramets.decision.schema import Decision, DecisionCategory, Option
from ramets.decision.tracker import DecisionTracker, _extract_keywords


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "store.db"
    db = GenetDB(db_path)
    db.init_schema()
    yield db
    db.close()


@pytest.fixture
def tracker(db):
    return DecisionTracker(db)


def _make_decision(
    question: str = "Which auth strategy?",
    branch: str = "feat/auth",
    commit_sha: str = "abc123",
) -> Decision:
    return Decision(
        branch=branch,
        category=DecisionCategory.architecture,
        question=question,
        options=[Option(label="JWT"), Option(label="Sessions")],
        chosen=0,
        commit_sha=commit_sha,
    )


class TestExtractKeywords:
    def test_removes_stop_words(self):
        kw = _extract_keywords("how does the auth module work")
        assert "how" not in kw
        assert "does" not in kw
        assert "the" not in kw
        assert "auth" in kw
        assert "module" in kw
        assert "work" in kw  # 4 chars, not a stop word

    def test_short_words_removed(self):
        kw = _extract_keywords("a is to be or go")
        # all are stop words or <= 2 chars
        assert len(kw) == 0

    def test_case_insensitive(self):
        kw = _extract_keywords("JWT Auth Strategy")
        assert "jwt" in kw
        assert "auth" in kw

    def test_strips_punctuation(self):
        kw = _extract_keywords("Which auth strategy?")
        assert "strategy" in kw


class TestHasSimilarDecision:
    def test_no_existing_decisions(self, tracker):
        """No similar decision when DB is empty."""
        assert not tracker.has_similar_decision("main", "abc", "auth strategy?")

    def test_same_commit_similar_question(self, tracker):
        """Detects duplicate on same commit with similar keywords."""
        d = _make_decision(question="Which auth strategy middleware layer?", commit_sha="abc123")
        tracker.record(d)

        # "auth strategy middleware" overlaps well with "auth middleware strategy"
        assert tracker.has_similar_decision(
            "feat/auth", "abc123", "Which auth middleware strategy approach?"
        )

    def test_same_commit_different_question(self, tracker):
        """Different question on same commit is not a duplicate."""
        d = _make_decision(question="Which auth strategy?", commit_sha="abc123")
        tracker.record(d)

        assert not tracker.has_similar_decision("feat/auth", "abc123", "Which database ORM to use?")

    def test_different_commit_same_question(self, tracker):
        """Same question on different commit is not a duplicate."""
        d = _make_decision(question="Which auth strategy?", commit_sha="abc123")
        tracker.record(d)

        assert not tracker.has_similar_decision("feat/auth", "def456", "Which auth strategy?")

    def test_empty_commit_sha(self, tracker):
        """Empty commit SHA always returns False."""
        d = _make_decision(commit_sha="abc123")
        tracker.record(d)
        assert not tracker.has_similar_decision("feat/auth", "", "auth strategy?")


class TestRecordIfNew:
    def test_records_new_decision(self, tracker):
        """Records decision when no duplicate exists."""
        d = _make_decision()
        result = tracker.record_if_new(d)
        assert result is not None
        assert result == d.id

    def test_skips_duplicate(self, tracker):
        """Skips recording when similar decision exists."""
        d1 = _make_decision(question="Which auth strategy middleware layer?", commit_sha="abc")
        tracker.record(d1)

        d2 = _make_decision(question="Which auth middleware strategy approach?", commit_sha="abc")
        result = tracker.record_if_new(d2)
        assert result is None

    def test_allows_different_commits(self, tracker):
        """Records decision for different commit even if similar question."""
        d1 = _make_decision(question="Which auth strategy?", commit_sha="abc")
        tracker.record(d1)

        d2 = _make_decision(question="Which auth strategy?", commit_sha="def")
        result = tracker.record_if_new(d2)
        assert result is not None
