"""SQLite persistence.

Leads are stored as JSON payloads with a few columns lifted out for querying.
The Pydantic model stays the single source of truth for shape and for the
Google-content boundary — see `PersistedModel` in models.py.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from .models import Lead, Stage, utcnow

DEFAULT_DB_PATH = Path("leads.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    place_id     TEXT PRIMARY KEY,
    city         TEXT NOT NULL,
    stage        TEXT NOT NULL,
    total_score  REAL,
    updated_at   TEXT NOT NULL,
    payload      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_leads_stage ON leads(stage);
CREATE INDEX IF NOT EXISTS idx_leads_city  ON leads(city);
CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(total_score);

-- Tracks Places API consumption so we can stay inside the India free tier.
CREATE TABLE IF NOT EXISTS api_usage (
    day   TEXT NOT NULL,
    sku   TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, sku)
);
"""


class LeadStore:
    def __init__(self, path: Path | str = DEFAULT_DB_PATH) -> None:
        self.path = Path(path)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> LeadStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- leads ------------------------------------------------------------

    def upsert(self, lead: Lead) -> None:
        self._conn.execute(
            """
            INSERT INTO leads (place_id, city, stage, total_score, updated_at, payload)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(place_id) DO UPDATE SET
                city        = excluded.city,
                stage       = excluded.stage,
                total_score = excluded.total_score,
                updated_at  = excluded.updated_at,
                payload     = excluded.payload
            """,
            (
                lead.place_id,
                lead.city,
                lead.stage.value,
                lead.score.total if lead.score else None,
                utcnow().isoformat(),
                lead.model_dump_json(),
            ),
        )
        self._conn.commit()

    def get(self, place_id: str) -> Lead | None:
        row = self._conn.execute(
            "SELECT payload FROM leads WHERE place_id = ?", (place_id,)
        ).fetchone()
        return Lead.model_validate_json(row["payload"]) if row else None

    def exists(self, place_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM leads WHERE place_id = ?", (place_id,)
        ).fetchone()
        return row is not None

    def all(self) -> Iterator[Lead]:
        for row in self._conn.execute("SELECT payload FROM leads ORDER BY rowid"):
            yield Lead.model_validate_json(row["payload"])

    def by_stage(self, *stages: Stage) -> Iterator[Lead]:
        placeholders = ",".join("?" for _ in stages)
        rows = self._conn.execute(
            f"SELECT payload FROM leads WHERE stage IN ({placeholders}) ORDER BY rowid",
            tuple(s.value for s in stages),
        )
        for row in rows:
            yield Lead.model_validate_json(row["payload"])

    def ranked(self, limit: int = 50) -> list[Lead]:
        """Highest-scoring qualified leads first — the operator's work queue."""
        rows = self._conn.execute(
            """
            SELECT payload FROM leads
            WHERE stage NOT IN (?, ?)
              AND total_score IS NOT NULL
            ORDER BY total_score DESC
            LIMIT ?
            """,
            (Stage.REJECTED.value, Stage.LOST.value, limit),
        )
        return [Lead.model_validate_json(r["payload"]) for r in rows]

    def counts_by_stage(self) -> dict[str, int]:
        rows = self._conn.execute("SELECT stage, COUNT(*) AS n FROM leads GROUP BY stage")
        return {r["stage"]: r["n"] for r in rows}

    # -- API budget -------------------------------------------------------

    def record_api_call(self, sku: str, count: int = 1) -> None:
        self._conn.execute(
            """
            INSERT INTO api_usage (day, sku, count) VALUES (?, ?, ?)
            ON CONFLICT(day, sku) DO UPDATE SET count = count + excluded.count
            """,
            (date.today().isoformat(), sku, count),
        )
        self._conn.commit()

    def usage_this_month(self) -> dict[str, int]:
        prefix = date.today().strftime("%Y-%m")
        rows = self._conn.execute(
            "SELECT sku, SUM(count) AS n FROM api_usage WHERE day LIKE ? GROUP BY sku",
            (f"{prefix}-%",),
        )
        return {r["sku"]: r["n"] for r in rows}

    # -- maintenance ------------------------------------------------------

    def rewrite_all(self) -> int:
        """Re-validate every payload through the current schema.

        Round-tripping applies model validators to stored rows, which is how the
        30-day geo expiry actually takes effect on old records.
        """
        changed = 0
        for lead in list(self.all()):
            before = lead.model_dump_json()
            revalidated = Lead.model_validate(json.loads(before))
            if revalidated.model_dump_json() != before:
                changed += 1
            self.upsert(revalidated)
        return changed


@contextmanager
def open_store(path: Path | str = DEFAULT_DB_PATH) -> Iterator[LeadStore]:
    store = LeadStore(path)
    try:
        yield store
    finally:
        store.close()
