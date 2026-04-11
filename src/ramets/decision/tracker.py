"""Decision tracker — CRUD, search, and chain traversal.

Records structured decisions in SQLite and provides query interfaces.
"""

from __future__ import annotations

import json
from typing import Optional

from ramets.core.db import GenetDB
from ramets.decision.schema import Decision, DecisionRelation, Option


class DecisionTracker:
    """Manages the decision graph stored in SQLite."""

    def __init__(self, db: GenetDB):
        self.db = db

    def record(self, decision: Decision) -> str:
        """Record a new decision. Returns the decision ID."""
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO decisions "
                "(id, branch, session_id, timestamp, category, question, "
                "options, chosen, rationale, confidence, status, "
                "superseded_by, context_files, commit_sha) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    decision.id,
                    decision.branch,
                    decision.session_id,
                    decision.timestamp.isoformat(),
                    decision.category.value,
                    decision.question,
                    json.dumps([o.model_dump() for o in decision.options]),
                    decision.chosen,
                    decision.rationale,
                    decision.confidence,
                    decision.status.value,
                    decision.superseded_by,
                    json.dumps(decision.context_files),
                    decision.commit_sha,
                ),
            )
        return decision.id

    def get(self, decision_id: str) -> Decision | None:
        """Get a decision by ID."""
        row = self.db.conn.execute(
            "SELECT * FROM decisions WHERE id = ?", (decision_id,)
        ).fetchone()
        if row is None:
            return None
        return _row_to_decision(dict(row))

    def query(
        self,
        branch: str | None = None,
        category: str | None = None,
        status: str = "active",
    ) -> list[Decision]:
        """Query decisions with filters."""
        sql = "SELECT * FROM decisions WHERE 1=1"
        params: list = []

        if branch:
            sql += " AND branch = ?"
            params.append(branch)
        if category:
            sql += " AND category = ?"
            params.append(category)
        if status:
            sql += " AND status = ?"
            params.append(status)

        sql += " ORDER BY timestamp DESC"
        rows = self.db.conn.execute(sql, params).fetchall()
        return [_row_to_decision(dict(r)) for r in rows]

    def search(self, query: str) -> list[Decision]:
        """Full-text search across questions, options, and rationale."""
        pattern = f"%{query}%"
        rows = self.db.conn.execute(
            "SELECT * FROM decisions WHERE "
            "question LIKE ? OR options LIKE ? OR rationale LIKE ? "
            "ORDER BY timestamp DESC",
            (pattern, pattern, pattern),
        ).fetchall()
        return [_row_to_decision(dict(r)) for r in rows]

    def supersede(self, old_id: str, new_decision: Decision) -> str:
        """Create a new decision that supersedes an existing one."""
        # Mark old as superseded
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE decisions SET status = 'superseded', superseded_by = ? WHERE id = ?",
                (new_decision.id, old_id),
            )

        # Record new decision
        self.record(new_decision)

        # Create edge
        self.add_edge(new_decision.id, old_id, DecisionRelation.supersedes)

        return new_decision.id

    def add_edge(self, source: str, target: str, relation: DecisionRelation) -> None:
        """Add a relationship between decisions (or decision → code node)."""
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO decision_edges (source, target, relation) "
                "VALUES (?, ?, ?)",
                (source, target, relation.value),
            )

    def decision_chain(self, decision_id: str, max_depth: int = 10) -> list[Decision]:
        """Trace the chain of decisions linked by led_to/supersedes."""
        visited: set[str] = set()
        chain: list[Decision] = []
        queue = [decision_id]

        while queue and len(chain) < max_depth:
            did = queue.pop(0)
            if did in visited:
                continue
            visited.add(did)

            decision = self.get(did)
            if decision:
                chain.append(decision)

            # Follow edges
            rows = self.db.conn.execute(
                "SELECT target FROM decision_edges WHERE source = ? "
                "AND relation IN ('led_to', 'supersedes')",
                (did,),
            ).fetchall()
            for r in rows:
                queue.append(r["target"])

        return chain

    def for_branch(self, branch: str) -> list[Decision]:
        """Get all active decisions for a branch."""
        return self.query(branch=branch, status="active")


def _row_to_decision(row: dict) -> Decision:
    """Convert a SQLite row to a Decision model."""
    options_raw = json.loads(row["options"])
    options = [Option(**o) for o in options_raw]
    context_files = json.loads(row["context_files"]) if row["context_files"] else []

    return Decision(
        id=row["id"],
        branch=row["branch"],
        session_id=row["session_id"],
        timestamp=row["timestamp"],
        category=row["category"],
        question=row["question"],
        options=options,
        chosen=row["chosen"],
        rationale=row["rationale"],
        confidence=row["confidence"],
        status=row["status"],
        superseded_by=row["superseded_by"],
        context_files=context_files,
        commit_sha=row["commit_sha"],
    )
