"""SQLite database — the genet's root system.

Single file stores everything: base graph (genet), branch snapshots (ramets),
delta log, decisions, sessions. WAL mode for concurrent worktree access.
"""

from __future__ import annotations

import json
import sqlite3
import zlib
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

SCHEMA_VERSION = 1

SCHEMA_SQL = """
-- WAL mode for concurrent reads from multiple worktrees
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ═══════════════════════════════════════════════════════════════
-- GENET: shared root graph (compressed blob)
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS genet (
    id          INTEGER PRIMARY KEY CHECK (id = 1),  -- singleton
    commit_sha  TEXT NOT NULL,
    graph_blob  BLOB NOT NULL,  -- zlib(json({nodes: [...], links: [...]}))
    node_count  INTEGER NOT NULL,
    edge_count  INTEGER NOT NULL,
    built_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ═══════════════════════════════════════════════════════════════
-- RAMETS: materialized per-branch graphs (genet + deltas applied)
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS ramets (
    branch      TEXT PRIMARY KEY,
    commit_sha  TEXT NOT NULL,
    graph_blob  BLOB NOT NULL,  -- zlib(json({nodes: [...], links: [...]}))
    node_count  INTEGER NOT NULL,
    edge_count  INTEGER NOT NULL,
    built_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ═══════════════════════════════════════════════════════════════
-- DELTA LOG: per-ramet changes relative to genet
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS ramet_deltas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    branch      TEXT NOT NULL,
    commit_sha  TEXT NOT NULL,
    timestamp   TEXT NOT NULL DEFAULT (datetime('now')),
    op          TEXT NOT NULL,      -- add_node, rm_node, mod_node, add_edge, rm_edge, mod_edge
    entity_type TEXT NOT NULL,      -- 'node' or 'edge'
    entity_id   TEXT NOT NULL,      -- node id, or 'source|target|relation' for edges
    payload     TEXT                -- JSON: full entity data for add/mod, null for rm
);

CREATE INDEX IF NOT EXISTS idx_deltas_branch ON ramet_deltas(branch);
CREATE INDEX IF NOT EXISTS idx_deltas_commit ON ramet_deltas(commit_sha);

-- ═══════════════════════════════════════════════════════════════
-- DECISIONS: structured tracking of AI suggestions and user choices
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS decisions (
    id              TEXT PRIMARY KEY,
    branch          TEXT NOT NULL,
    session_id      TEXT,
    timestamp       TEXT NOT NULL DEFAULT (datetime('now')),
    category        TEXT NOT NULL,
    question        TEXT NOT NULL,
    options         TEXT NOT NULL,  -- JSON array of option objects
    chosen          INTEGER NOT NULL,
    rationale       TEXT,
    confidence      REAL,
    status          TEXT NOT NULL DEFAULT 'active',
    superseded_by   TEXT,
    context_files   TEXT,  -- JSON array of file paths
    commit_sha      TEXT
);

CREATE INDEX IF NOT EXISTS idx_decisions_branch ON decisions(branch);
CREATE INDEX IF NOT EXISTS idx_decisions_category ON decisions(category);
CREATE INDEX IF NOT EXISTS idx_decisions_status ON decisions(status);

CREATE TABLE IF NOT EXISTS decision_edges (
    source      TEXT NOT NULL,
    target      TEXT NOT NULL,
    relation    TEXT NOT NULL,
    timestamp   TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (source, target, relation)
);

CREATE INDEX IF NOT EXISTS idx_decision_edges_source ON decision_edges(source);

-- ═══════════════════════════════════════════════════════════════
-- SESSIONS: AI coding session tracking
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    tool        TEXT NOT NULL,      -- 'claude-code', 'cursor', 'codex'
    branch      TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    ended_at    TEXT,
    worktree    TEXT,
    summary     TEXT,
    stats       TEXT  -- JSON
);

-- ═══════════════════════════════════════════════════════════════
-- BRANCH REGISTRY: which ramets are alive
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS branches (
    name        TEXT PRIMARY KEY,
    merge_base  TEXT,
    last_built  TEXT,
    delta_count INTEGER DEFAULT 0,
    worktree    TEXT
);

-- Schema version for migrations
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);
"""


class GenetDB:
    """Connection to the genet database (the root system)."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def init_schema(self) -> None:
        """Create all tables if they don't exist."""
        self.conn.executescript(SCHEMA_SQL)
        # Set schema version
        cur = self.conn.execute("SELECT version FROM schema_version LIMIT 1")
        if cur.fetchone() is None:
            self.conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
        self.conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for a transaction."""
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    # ── Genet (base graph) operations ──────────────────────────────

    def store_genet(self, graph_data: dict, commit_sha: str) -> None:
        """Store the base graph (genet) as a compressed blob."""
        blob = compress_graph(graph_data)
        nodes = len(graph_data.get("nodes", []))
        edges = len(graph_data.get("links", []))
        with self.transaction() as conn:
            conn.execute("DELETE FROM genet")
            conn.execute(
                "INSERT INTO genet (id, commit_sha, graph_blob, node_count, edge_count) "
                "VALUES (1, ?, ?, ?, ?)",
                (commit_sha, blob, nodes, edges),
            )

    def load_genet(self) -> dict | None:
        """Load the base graph. Returns None if no genet exists."""
        row = self.conn.execute("SELECT graph_blob, commit_sha FROM genet WHERE id = 1").fetchone()
        if row is None:
            return None
        return decompress_graph(row["graph_blob"])

    def genet_meta(self) -> dict | None:
        """Get genet metadata without loading the full graph."""
        row = self.conn.execute(
            "SELECT commit_sha, node_count, edge_count, built_at FROM genet WHERE id = 1"
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    # ── Ramet (branch snapshot) operations ─────────────────────────

    def store_ramet(self, branch: str, graph_data: dict, commit_sha: str) -> None:
        """Store a materialized branch graph (ramet)."""
        blob = compress_graph(graph_data)
        nodes = len(graph_data.get("nodes", []))
        edges = len(graph_data.get("links", []))
        with self.transaction() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO ramets "
                "(branch, commit_sha, graph_blob, node_count, edge_count) "
                "VALUES (?, ?, ?, ?, ?)",
                (branch, commit_sha, blob, nodes, edges),
            )

    def load_ramet(self, branch: str) -> dict | None:
        """Load a materialized branch graph. Returns None if not cached."""
        row = self.conn.execute(
            "SELECT graph_blob FROM ramets WHERE branch = ?", (branch,)
        ).fetchone()
        if row is None:
            return None
        return decompress_graph(row["graph_blob"])

    def ramet_meta(self, branch: str) -> dict | None:
        """Get ramet metadata without loading the full graph."""
        row = self.conn.execute(
            "SELECT commit_sha, node_count, edge_count, built_at FROM ramets WHERE branch = ?",
            (branch,),
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    def list_ramets(self) -> list[dict]:
        """List all cached ramets."""
        rows = self.conn.execute(
            "SELECT branch, commit_sha, node_count, edge_count, built_at FROM ramets"
        ).fetchall()
        return [dict(r) for r in rows]

    def delete_ramet(self, branch: str) -> None:
        """Delete a cached ramet."""
        with self.transaction() as conn:
            conn.execute("DELETE FROM ramets WHERE branch = ?", (branch,))
            conn.execute("DELETE FROM ramet_deltas WHERE branch = ?", (branch,))
            conn.execute("DELETE FROM branches WHERE name = ?", (branch,))

    # ── Delta operations ───────────────────────────────────────────

    def append_deltas(self, branch: str, commit_sha: str, deltas: list[dict]) -> None:
        """Append deltas for a branch."""
        with self.transaction() as conn:
            for d in deltas:
                conn.execute(
                    "INSERT INTO ramet_deltas (branch, commit_sha, op, entity_type, entity_id, payload) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        branch,
                        commit_sha,
                        d["op"],
                        d["entity_type"],
                        d["entity_id"],
                        json.dumps(d.get("payload")) if d.get("payload") else None,
                    ),
                )
            # Update branch registry
            conn.execute(
                "INSERT OR REPLACE INTO branches (name, last_built, delta_count) "
                "VALUES (?, datetime('now'), "
                "(SELECT COUNT(*) FROM ramet_deltas WHERE branch = ?))",
                (branch, branch),
            )

    def load_deltas(self, branch: str) -> list[dict]:
        """Load all deltas for a branch, ordered by id."""
        rows = self.conn.execute(
            "SELECT op, entity_type, entity_id, payload FROM ramet_deltas "
            "WHERE branch = ? ORDER BY id",
            (branch,),
        ).fetchall()
        result = []
        for r in rows:
            d: dict[str, Any] = {
                "op": r["op"],
                "entity_type": r["entity_type"],
                "entity_id": r["entity_id"],
            }
            if r["payload"]:
                d["payload"] = json.loads(r["payload"])
            result.append(d)
        return result

    def delta_count(self, branch: str) -> int:
        """Count deltas for a branch."""
        row = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM ramet_deltas WHERE branch = ?", (branch,)
        ).fetchone()
        return row["cnt"] if row else 0

    # ── Branch registry ────────────────────────────────────────────

    def register_branch(
        self, name: str, merge_base: str | None = None, worktree: str | None = None
    ) -> None:
        """Register a branch in the registry."""
        with self.transaction() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO branches (name, merge_base, worktree) VALUES (?, ?, ?)",
                (name, merge_base, worktree),
            )

    def list_branches(self) -> list[dict]:
        """List all registered branches."""
        rows = self.conn.execute("SELECT * FROM branches").fetchall()
        return [dict(r) for r in rows]


# ── Compression helpers ────────────────────────────────────────────


def compress_graph(graph_data: dict) -> bytes:
    """Compress a graph dict to a zlib blob."""
    return zlib.compress(json.dumps(graph_data, separators=(",", ":")).encode(), level=6)


def decompress_graph(blob: bytes) -> dict:
    """Decompress a zlib blob to a graph dict."""
    return json.loads(zlib.decompress(blob))
