"""Small, dependency-free SQLite data layer for RF Finder."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
    role TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    refresh_token_hash TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL, revoked_at TEXT
);
CREATE TABLE IF NOT EXISTS access_tokens (
    token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, driver TEXT NOT NULL, serial TEXT,
    center_frequency_hz REAL, sample_rate_hz REAL, active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS captures (
    id TEXT PRIMARY KEY, device_id TEXT REFERENCES devices(id) ON DELETE SET NULL,
    started_at TEXT NOT NULL, center_frequency_hz REAL NOT NULL, sample_rate_hz REAL NOT NULL,
    latitude REAL, longitude REAL, source TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS measurements (
    id TEXT PRIMARY KEY, capture_id TEXT REFERENCES captures(id) ON DELETE CASCADE,
    timestamp TEXT NOT NULL, center_frequency_hz REAL NOT NULL, peak_power_db REAL NOT NULL,
    noise_floor_db REAL NOT NULL, snr_db REAL NOT NULL, bandwidth_hz REAL NOT NULL,
    peak_magnitude REAL NOT NULL, frame_index INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, action TEXT NOT NULL,
    resource TEXT, resource_id TEXT, ip_address TEXT, metadata_json TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_measurements_frequency ON measurements(center_frequency_hz);
CREATE INDEX IF NOT EXISTS idx_measurements_time ON measurements(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_events(created_at);
"""


class Database:
    def __init__(self, path: str = "data/database/rf_finder.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        with self.connect() as conn:
            cursor = conn.execute(sql, params)
            conn.commit()
            return cursor

    def fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(sql, params).fetchone()

    def fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(sql, params).fetchall()
