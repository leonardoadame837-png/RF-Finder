"""Persistence repositories for users, devices, captures and measurements."""
from __future__ import annotations

import json
import uuid
from datetime import datetime

from app.auth.models import User
from .sqlite import Database


class UserRepository:
    def __init__(self, db: Database): self.db = db

    def create(self, user: User) -> User:
        self.db.execute("INSERT INTO users VALUES (?,?,?,?,?,?)", (user.id, user.username, user.password_hash, user.role, int(user.active), (user.created_at or datetime.utcnow()).isoformat()))
        return user

    def by_username(self, username: str) -> User | None:
        row = self.db.fetchone("SELECT * FROM users WHERE username=?", (username.lower(),))
        return User(row["id"], row["username"], row["password_hash"], row["role"], bool(row["active"]), datetime.fromisoformat(row["created_at"])) if row else None

    def by_id(self, user_id: str) -> User | None:
        row = self.db.fetchone("SELECT * FROM users WHERE id=?", (user_id,))
        return User(row["id"], row["username"], row["password_hash"], row["role"], bool(row["active"]), datetime.fromisoformat(row["created_at"])) if row else None


class DeviceRepository:
    def __init__(self, db: Database): self.db = db

    def create(self, name: str, driver: str, serial: str | None = None, center_frequency_hz: float | None = None, sample_rate_hz: float | None = None) -> dict:
        device_id = str(uuid.uuid4()); now = datetime.utcnow().isoformat()
        self.db.execute("INSERT INTO devices VALUES (?,?,?,?,?,?,?,?)", (device_id, name, driver, serial, center_frequency_hz, sample_rate_hz, 1, now))
        return self.get(device_id)

    def get(self, device_id: str) -> dict | None:
        row = self.db.fetchone("SELECT * FROM devices WHERE id=?", (device_id,))
        return dict(row) if row else None

    def list(self) -> list[dict]: return [dict(r) for r in self.db.fetchall("SELECT * FROM devices ORDER BY created_at DESC")]


class MeasurementRepository:
    def __init__(self, db: Database): self.db = db

    def add(self, detection, capture_id: str | None = None) -> str:
        measurement_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO measurements VALUES (?,?,?,?,?,?,?,?,?,?)", (measurement_id, capture_id, datetime.utcnow().isoformat(), detection.center_frequency_hz, detection.peak_power_db, detection.noise_floor_db, detection.snr_db, detection.bandwidth_hz, detection.peak_magnitude, detection.timestamp_frame))
        return measurement_id

    def recent(self, limit: int = 100) -> list[dict]:
        limit = max(1, min(limit, 1000))
        return [dict(r) for r in self.db.fetchall("SELECT * FROM measurements ORDER BY timestamp DESC LIMIT ?", (limit,))]


class AuditRepository:
    def __init__(self, db: Database): self.db = db

    def record(self, action: str, user_id: str | None = None, resource: str | None = None, resource_id: str | None = None, ip_address: str | None = None, metadata: dict | None = None) -> None:
        self.db.execute("INSERT INTO audit_events(user_id,action,resource,resource_id,ip_address,metadata_json,created_at) VALUES (?,?,?,?,?,?,?)", (user_id, action, resource, resource_id, ip_address, json.dumps(metadata or {}, separators=(",", ":")), datetime.utcnow().isoformat()))
