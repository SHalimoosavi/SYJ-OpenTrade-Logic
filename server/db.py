"""
SYJ OpenTrade Logic - SQLite persistence layer
================================================
stdlib-only (sqlite3). Stores classification history so results are
auditable after the fact, per the platform's audit-trail requirement.

Schema is intentionally simple and portable: this is the same shape you'd
map to a SQLAlchemy model in v0.3.0 once a real Postgres/SQLAlchemy stack
is available.
"""

import json
import sqlite3
import time
from contextlib import contextmanager
from typing import Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS classifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_description TEXT NOT NULL,
    final_code TEXT,
    final_description TEXT,
    confidence REAL,
    is_classified INTEGER NOT NULL,
    duty_rate TEXT,
    unresolved_reason TEXT,
    result_json TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_classifications_created_at
    ON classifications(created_at DESC);
"""


class ClassificationStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def save(self, result_dict: dict) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO classifications
                    (product_description, final_code, final_description,
                     confidence, is_classified, duty_rate, unresolved_reason,
                     result_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result_dict["product_description"],
                    result_dict.get("final_code"),
                    result_dict.get("final_description"),
                    result_dict.get("confidence"),
                    1 if result_dict.get("is_classified") else 0,
                    result_dict.get("duty_rate"),
                    result_dict.get("unresolved_reason"),
                    json.dumps(result_dict),
                    time.time(),
                ),
            )
            return cur.lastrowid

    def get(self, record_id: int) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM classifications WHERE id = ?", (record_id,)
            ).fetchone()
            if row is None:
                return None
            return self._row_to_dict(row)

    def list(self, limit: int = 50, offset: int = 0) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM classifications ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]

    def delete(self, record_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM classifications WHERE id = ?", (record_id,))
            return cur.rowcount > 0

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) as c FROM classifications").fetchone()
            return row["c"]

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        d["is_classified"] = bool(d["is_classified"])
        d["result"] = json.loads(d.pop("result_json"))
        return d
