"""Local SQLite investigation records for correlating RF observations."""

from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from datetime import datetime, timezone


class InvestigationStore:
    def __init__(self, database_path: str):
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS investigations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS investigation_observations (
                investigation_id TEXT NOT NULL,
                observation_id INTEGER NOT NULL,
                PRIMARY KEY (investigation_id, observation_id)
            )""")

    def create(self, title: str, notes: str = "") -> dict:
        now = datetime.now(timezone.utc).isoformat()
        item = {"id": uuid.uuid4().hex, "title": title.strip() or "RF investigation", "status": "open", "notes": notes, "created_at": now, "updated_at": now}
        with sqlite3.connect(self.path) as conn:
            conn.execute("INSERT INTO investigations VALUES (?, ?, ?, ?, ?, ?)", tuple(item.values()))
        return item

    def list(self) -> list[dict]:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM investigations ORDER BY updated_at DESC").fetchall()
        return [dict(r) for r in rows]

    def get(self, investigation_id: str) -> dict | None:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM investigations WHERE id = ?", (investigation_id,)).fetchone()
            if not row:
                return None
            item = dict(row)
            obs = conn.execute("SELECT observation_id FROM investigation_observations WHERE investigation_id = ? ORDER BY observation_id", (investigation_id,)).fetchall()
            item["observation_ids"] = [r[0] for r in obs]
            return item

    def attach_observation(self, investigation_id: str, observation_id: int) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.path) as conn:
            exists = conn.execute("SELECT 1 FROM investigations WHERE id = ?", (investigation_id,)).fetchone()
            if not exists:
                return False
            conn.execute("INSERT OR IGNORE INTO investigation_observations VALUES (?, ?)", (investigation_id, int(observation_id)))
            conn.execute("UPDATE investigations SET updated_at = ? WHERE id = ?", (now, investigation_id))
        return True
