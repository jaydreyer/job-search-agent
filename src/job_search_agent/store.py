"""SQLite store to remember which postings we've already seen and scored.

Lets the daily digest surface only *new* matches instead of repeating yesterday's.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .config import ROOT
from .models import ScoredJob

DEFAULT_DB = ROOT / "data" / "seen.db"


class SeenStore:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or DEFAULT_DB
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS seen (
                fingerprint TEXT PRIMARY KEY,
                title TEXT, company TEXT, url TEXT,
                score INTEGER, first_seen TEXT
            )"""
        )
        self.conn.commit()

    def is_new(self, fingerprint: str) -> bool:
        cur = self.conn.execute("SELECT 1 FROM seen WHERE fingerprint = ?", (fingerprint,))
        return cur.fetchone() is None

    def filter_new(self, scored: list[ScoredJob]) -> list[ScoredJob]:
        return [s for s in scored if self.is_new(s.job.fingerprint)]

    def record(self, scored: list[ScoredJob]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.conn.executemany(
            "INSERT OR IGNORE INTO seen VALUES (?, ?, ?, ?, ?, ?)",
            [
                (s.job.fingerprint, s.job.title, s.job.company, s.job.url, s.score, now)
                for s in scored
            ],
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
