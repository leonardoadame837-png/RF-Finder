"""SQLite persistence for RF observations."""

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from app.observation import RFObservation


class ObservationStore:
    """Small SQLite event store for measurements used by the tactical view."""

    def __init__(self, database_path: str):
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    frequency_hz REAL NOT NULL,
                    peak_power_db REAL NOT NULL,
                    noise_floor_db REAL NOT NULL,
                    snr_db REAL NOT NULL,
                    bandwidth_hz REAL NOT NULL,
                    latitude REAL,
                    longitude REAL,
                    altitude_m REAL,
                    bearing_deg REAL,
                    source TEXT NOT NULL,
                    signal_class TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    evidence TEXT NOT NULL,
                    simulated INTEGER NOT NULL DEFAULT 0
                )"""
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_obs_time ON observations(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_obs_freq ON observations(frequency_hz)")

    def add(self, observation: RFObservation) -> int:
        data = observation.to_dict()
        with self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO observations
                (timestamp, frequency_hz, peak_power_db, noise_floor_db, snr_db,
                 bandwidth_hz, latitude, longitude, altitude_m, bearing_deg, source,
                 signal_class, confidence, evidence, simulated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (*[data[k] for k in (
                    "timestamp", "frequency_hz", "peak_power_db", "noise_floor_db",
                    "snr_db", "bandwidth_hz", "latitude", "longitude", "altitude_m",
                    "bearing_deg", "source", "signal_class", "confidence", "evidence"
                )], int(data["simulated"])),
            )
            return int(cur.lastrowid)

    def recent(self, limit: int = 500) -> list[dict]:
        limit = max(1, min(int(limit), 5000))
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM observations ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in reversed(rows)]
