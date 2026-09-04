"""Local SQLite investigation records for correlating RF observations."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class InvestigationStore:
    """Persist investigation metadata and RF observation associations in SQLite."""

    def __init__(self, database_path: str):
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _initialize(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS investigations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS investigation_observations (
                    investigation_id INTEGER NOT NULL,
                    observation_id INTEGER NOT NULL,
                    PRIMARY KEY (investigation_id, observation_id)
                )"""
            )

            # Older builds used UUID text IDs. Migrate that schema once so the
            # public API has one predictable numeric identifier type.
            columns = conn.execute("PRAGMA table_info(investigations)").fetchall()
            id_column = next((column for column in columns if column[1] == "id"), None)
            if id_column and id_column[2].upper() == "TEXT":
                self._migrate_text_ids(conn)

    @staticmethod
    def _migrate_text_ids(conn: sqlite3.Connection) -> None:
        conn.execute("ALTER TABLE investigations RENAME TO investigations_legacy")
        conn.execute(
            """CREATE TABLE investigations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )"""
        )
        rows = conn.execute(
            "SELECT id, title, status, notes, created_at, updated_at "
            "FROM investigations_legacy ORDER BY created_at, rowid"
        ).fetchall()
        id_map: dict[str, int] = {}
        for old_id, title, status, notes, created_at, updated_at in rows:
            cursor = conn.execute(
                "INSERT INTO investigations(title, status, notes, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (title, status, notes, created_at, updated_at),
            )
            id_map[str(old_id)] = int(cursor.lastrowid)

        legacy_links = conn.execute(
            "SELECT investigation_id, observation_id FROM investigation_observations"
        ).fetchall()
        conn.execute("DROP TABLE investigation_observations")
        conn.execute("DROP TABLE investigations_legacy")
        conn.execute(
            """CREATE TABLE investigation_observations (
                investigation_id INTEGER NOT NULL,
                observation_id INTEGER NOT NULL,
                PRIMARY KEY (investigation_id, observation_id)
            )"""
        )
        for old_id, observation_id in legacy_links:
            new_id = id_map.get(str(old_id))
            if new_id is not None:
                conn.execute(
                    "INSERT OR IGNORE INTO investigation_observations VALUES (?, ?)",
                    (new_id, int(observation_id)),
                )

    def create(self, title: str, notes: str = "") -> dict:
        now = datetime.now(timezone.utc).isoformat()
        title = title.strip() or "RF investigation"
        with sqlite3.connect(self.path) as conn:
            cursor = conn.execute(
                """INSERT INTO investigations
                   (title, status, notes, created_at, updated_at)
                   VALUES (?, 'open', ?, ?, ?)""",
                (title, notes, now, now),
            )
            investigation_id = int(cursor.lastrowid)
        return self.get(investigation_id)  # type: ignore[return-value]

    def list(self) -> list[dict]:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM investigations ORDER BY updated_at DESC, id DESC"
            ).fetchall()
        return [dict(row) | {"observation_ids": self._observation_ids(dict(row)["id"])} for row in rows]

    def _observation_ids(self, investigation_id: int) -> list[int]:
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute(
                """SELECT observation_id FROM investigation_observations
                   WHERE investigation_id = ? ORDER BY observation_id""",
                (int(investigation_id),),
            ).fetchall()
        return [int(row[0]) for row in rows]

    def get(self, investigation_id: int) -> dict | None:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM investigations WHERE id = ?", (int(investigation_id),)
            ).fetchone()
        if row is None:
            return None
        item = dict(row)
        item["observation_ids"] = self._observation_ids(item["id"])
        return item

    def attach_observation(self, investigation_id: int, observation_id: int) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.path) as conn:
            exists = conn.execute(
                "SELECT 1 FROM investigations WHERE id = ?", (int(investigation_id),)
            ).fetchone()
            if not exists:
                return False
            conn.execute(
                "INSERT OR IGNORE INTO investigation_observations VALUES (?, ?)",
                (int(investigation_id), int(observation_id)),
            )
            conn.execute(
                "UPDATE investigations SET updated_at = ? WHERE id = ?",
                (now, int(investigation_id)),
            )
        return True
