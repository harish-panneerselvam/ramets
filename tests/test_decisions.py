"""Tests for decision tracking (decision/tracker.py, decision/schema.py)."""

import pytest

from ramets.core.db import GenetDB
from ramets.decision.schema import (
    Decision,
    DecisionCategory,
    DecisionRelation,
    DecisionStatus,
    Option,
    Proposer,
)
from ramets.decision.tracker import DecisionTracker


@pytest.fixture
def db(tmp_path):
    """Create a fresh database for each test."""
    db_path = tmp_path / "store.db"
    db = GenetDB(db_path)
    db.init_schema()
    yield db
    db.close()


@pytest.fixture
def tracker(db):
    """Create a decision tracker."""
    return DecisionTracker(db)


@pytest.fixture
def sample_decision():
    """A minimal decision for testing."""
    return Decision(
        branch="feat/auth",
        category=DecisionCategory.architecture,
        question="Which auth strategy?",
        options=[
            Option(
                label="JWT",
                description="Stateless tokens",
                proposed_by=Proposer.claude,
                pros=["Stateless", "Scalable"],
                cons=["Can't revoke easily"],
                estimated_effort="medium",
            ),
            Option(
                label="Session cookies",
                description="Server-side sessions",
                proposed_by=Proposer.user,
                pros=["Easy to revoke"],
                cons=["Requires session store"],
            ),
        ],
        chosen=0,
        rationale="Stateless architecture fits our microservices design",
        confidence=0.85,
        context_files=["src/auth.py", "src/middleware.py"],
        commit_sha="abc123",
    )


class TestDecisionSchema:
    def test_auto_id(self):
        """Decisions get auto-generated IDs."""
        d1 = Decision(branch="main", category="implementation", question="Q1", options=[], chosen=0)
        d2 = Decision(branch="main", category="implementation", question="Q2", options=[], chosen=0)
        assert d1.id != d2.id
        assert len(d1.id) == 12  # hex[:12]

    def test_chosen_option(self, sample_decision):
        """chosen_option property returns the correct option."""
        assert sample_decision.chosen_option.label == "JWT"

    def test_default_status(self, sample_decision):
        """Default status is active."""
        assert sample_decision.status == DecisionStatus.active

    def test_category_enum(self):
        """All expected categories exist."""
        assert DecisionCategory.architecture.value == "architecture"
        assert DecisionCategory.dependency.value == "dependency"
        assert DecisionCategory.performance.value == "performance"

    def test_option_model(self):
        """Option model works with minimal fields."""
        opt = Option(label="Quick fix")
        assert opt.label == "Quick fix"
        assert opt.pros == []
        assert opt.cons == []
        assert opt.proposed_by == Proposer.user


class TestDecisionTracker:
    def test_record_and_get(self, tracker, sample_decision):
        """Record a decision and retrieve it."""
        did = tracker.record(sample_decision)
        assert did == sample_decision.id

        loaded = tracker.get(did)
        assert loaded is not None
        assert loaded.question == "Which auth strategy?"
        assert loaded.chosen == 0
        assert len(loaded.options) == 2
        assert loaded.options[0].label == "JWT"
        assert loaded.options[0].pros == ["Stateless", "Scalable"]
        assert loaded.confidence == 0.85

    def test_get_missing(self, tracker):
        """Getting a non-existent decision returns None."""
        assert tracker.get("nonexistent") is None

    def test_query_by_branch(self, tracker, sample_decision):
        """Query decisions filtered by branch."""
        tracker.record(sample_decision)

        # Create another decision on a different branch
        other = Decision(
            branch="feat/db",
            category="dependency",
            question="Which DB?",
            options=[Option(label="PostgreSQL"), Option(label="SQLite")],
            chosen=1,
        )
        tracker.record(other)

        results = tracker.query(branch="feat/auth")
        assert len(results) == 1
        assert results[0].question == "Which auth strategy?"

    def test_query_by_category(self, tracker, sample_decision):
        """Query decisions filtered by category."""
        tracker.record(sample_decision)

        results = tracker.query(branch="feat/auth", category="architecture")
        assert len(results) == 1

        results = tracker.query(branch="feat/auth", category="implementation")
        assert len(results) == 0

    def test_query_by_status(self, tracker, sample_decision):
        """Query decisions filtered by status."""
        tracker.record(sample_decision)

        results = tracker.query(branch="feat/auth", status="active")
        assert len(results) == 1

        results = tracker.query(branch="feat/auth", status="superseded")
        assert len(results) == 0

    def test_search(self, tracker, sample_decision):
        """Full-text search across decisions."""
        tracker.record(sample_decision)

        results = tracker.search("auth strategy")
        assert len(results) == 1

        results = tracker.search("JWT")
        assert len(results) == 1

        results = tracker.search("microservices")
        assert len(results) == 1

        results = tracker.search("nonexistent-term-xyz")
        assert len(results) == 0

    def test_supersede(self, tracker, sample_decision):
        """Superseding marks old decision and creates new one."""
        tracker.record(sample_decision)

        new_decision = Decision(
            branch="feat/auth",
            category="architecture",
            question="Revised auth strategy",
            options=[
                Option(label="OAuth2"),
                Option(label="API Keys"),
            ],
            chosen=0,
            rationale="Need third-party auth support",
        )

        new_id = tracker.supersede(sample_decision.id, new_decision)

        # Old decision should be superseded
        old = tracker.get(sample_decision.id)
        assert old.status == DecisionStatus.superseded
        assert old.superseded_by == new_id

        # New decision should be active
        new = tracker.get(new_id)
        assert new.status == DecisionStatus.active
        assert new.question == "Revised auth strategy"

    def test_decision_chain(self, tracker, sample_decision):
        """Trace a chain of related decisions."""
        tracker.record(sample_decision)

        d2 = Decision(
            branch="feat/auth",
            category="implementation",
            question="JWT library?",
            options=[Option(label="PyJWT"), Option(label="python-jose")],
            chosen=0,
        )
        tracker.record(d2)
        tracker.add_edge(sample_decision.id, d2.id, DecisionRelation.led_to)

        chain = tracker.decision_chain(sample_decision.id)
        assert len(chain) == 2
        assert chain[0].id == sample_decision.id
        assert chain[1].id == d2.id

    def test_for_branch(self, tracker, sample_decision):
        """Get all active decisions for a branch."""
        tracker.record(sample_decision)

        # Add a superseded one
        old = Decision(
            branch="feat/auth",
            category="implementation",
            question="Old question",
            options=[Option(label="A")],
            chosen=0,
            status="superseded",
        )
        tracker.record(old)

        results = tracker.for_branch("feat/auth")
        assert len(results) == 1
        assert results[0].status == DecisionStatus.active

    def test_context_files_roundtrip(self, tracker, sample_decision):
        """Context files survive storage and retrieval."""
        tracker.record(sample_decision)
        loaded = tracker.get(sample_decision.id)
        assert loaded.context_files == ["src/auth.py", "src/middleware.py"]
