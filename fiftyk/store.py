"""SQLite persistence.

Opportunities are stored as JSON payloads with a few columns lifted out for
querying. The Pydantic models stay the single source of truth for shape.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .models import Opportunity, Stage
from .provenance import utcnow

DEFAULT_DB_PATH = Path("fiftyk.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS opportunities (
    key        TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    category   TEXT NOT NULL,
    stage      TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    payload    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_opp_stage    ON opportunities(stage);
CREATE INDEX IF NOT EXISTS idx_opp_category ON opportunities(category);

-- Append-only log of verdict changes, so the reasoning is auditable over time
-- rather than silently overwritten each run.
CREATE TABLE IF NOT EXISTS verdict_log (
    key        TEXT NOT NULL,
    verdict    TEXT NOT NULL,
    summary    TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_verdict_key ON verdict_log(key);
"""


class Store:
    def __init__(self, path: Path | str = DEFAULT_DB_PATH) -> None:
        self.path = Path(path)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def upsert(self, opportunity: Opportunity) -> None:
        self._conn.execute(
            """
            INSERT INTO opportunities (key, name, category, stage, updated_at, payload)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                name       = excluded.name,
                category   = excluded.category,
                stage      = excluded.stage,
                updated_at = excluded.updated_at,
                payload    = excluded.payload
            """,
            (
                opportunity.key,
                opportunity.name,
                opportunity.category,
                opportunity.stage.value,
                utcnow().isoformat(),
                opportunity.model_dump_json(),
            ),
        )
        self._conn.commit()

    def get(self, key: str) -> Opportunity | None:
        row = self._conn.execute(
            "SELECT payload FROM opportunities WHERE key = ?", (key,)
        ).fetchone()
        return Opportunity.model_validate_json(row["payload"]) if row else None

    def all(self) -> Iterator[Opportunity]:
        for row in self._conn.execute("SELECT payload FROM opportunities ORDER BY key"):
            yield Opportunity.model_validate_json(row["payload"])

    def by_stage(self, *stages: Stage) -> Iterator[Opportunity]:
        placeholders = ",".join("?" for _ in stages)
        rows = self._conn.execute(
            f"SELECT payload FROM opportunities WHERE stage IN ({placeholders}) ORDER BY key",
            tuple(s.value for s in stages),
        )
        for row in rows:
            yield Opportunity.model_validate_json(row["payload"])

    def counts_by_stage(self) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT stage, COUNT(*) AS n FROM opportunities GROUP BY stage"
        )
        return {r["stage"]: r["n"] for r in rows}

    def log_verdict(self, key: str, verdict: str, summary: str) -> None:
        """Append a verdict. History is kept so changes of mind stay visible."""
        self._conn.execute(
            "INSERT INTO verdict_log (key, verdict, summary, recorded_at) VALUES (?, ?, ?, ?)",
            (key, verdict, summary, utcnow().isoformat()),
        )
        self._conn.commit()

    def verdict_history(self, key: str) -> list[dict[str, str]]:
        rows = self._conn.execute(
            "SELECT verdict, summary, recorded_at FROM verdict_log WHERE key = ? ORDER BY recorded_at",
            (key,),
        )
        return [dict(r) for r in rows]

    def total_net_monthly(self) -> float:
        """Actual realised net across everything live, latest month only."""
        total = 0.0
        for opportunity in self.by_stage(Stage.LIVE, Stage.COMMITTED):
            latest = opportunity.latest_actual
            if latest:
                total += latest.net_inr
        return total


@contextmanager
def open_store(path: Path | str = DEFAULT_DB_PATH) -> Iterator[Store]:
    store = Store(path)
    try:
        yield store
    finally:
        store.close()
