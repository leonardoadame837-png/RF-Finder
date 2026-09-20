"""RF Finder Vision contracts for camera sources and timestamp correlation."""
from __future__ import annotations
import os, re, sqlite3
from datetime import datetime, timezone
from pathlib import Path

ALLOWED_CAMERA_PROTOCOLS = frozenset({"rtsp", "rtsps", "onvif"})
_SECRET_PREFIX = "RF_FINDER_CAMERA_"
_HOST_RE = re.compile(r"^[A-Za-z0-9._:-]{1,253}$")

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def validate_camera_host(host: str) -> str:
    host = str(host or "").strip()
    if not host or not _HOST_RE.fullmatch(host):
        raise ValueError("Invalid camera host")
    return host

def validate_camera_protocol(protocol: str) -> str:
    protocol = str(protocol or "").strip().lower()
    if protocol not in ALLOWED_CAMERA_PROTOCOLS:
        raise ValueError("Unsupported camera protocol")
    return protocol

def validate_camera_port(port: int) -> int:
    port = int(port)
    if not 1 <= port <= 65535:
        raise ValueError("Invalid camera port")
    return port

def secret_env_name(camera_id: int) -> str:
    return f"{_SECRET_PREFIX}{int(camera_id)}_PASSWORD"

def build_server_side_stream_reference(camera: dict) -> dict:
    return {
        "protocol": camera["protocol"],
        "host": camera["host"],
        "port": camera["port"],
        "credential_env": secret_env_name(camera["id"]) if camera.get("username") else None,
        "broker_required": True,
    }

def validate_secret_reference(camera_id: int) -> bool:
    return bool(os.getenv(secret_env_name(camera_id)))

class CameraRegistry:
    """Persist camera metadata without persisting camera passwords."""
    def __init__(self, database_path: str):
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _initialize(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS cameras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                host TEXT NOT NULL,
                port INTEGER NOT NULL,
                protocol TEXT NOT NULL,
                username TEXT NOT NULL DEFAULT '',
                stream_path TEXT NOT NULL DEFAULT '/',
                audio_enabled INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )""")
            columns = {row[1] for row in conn.execute("PRAGMA table_info(cameras)").fetchall()}
            if "stream_path" not in columns:
                conn.execute("ALTER TABLE cameras ADD COLUMN stream_path TEXT NOT NULL DEFAULT '/'")

    def create(self, *, name: str, host: str, port: int = 554,
               protocol: str = "rtsp", username: str = "", stream_path: str = "/",
               audio_enabled: bool = False) -> dict:
        name = str(name or "").strip() or "RF Camera"
        host = validate_camera_host(host)
        port = validate_camera_port(port)
        protocol = validate_camera_protocol(protocol)
        username = str(username or "").strip()
        stream_path = str(stream_path or "/").strip() or "/"
        if not stream_path.startswith("/"):
            stream_path = "/" + stream_path
        if len(stream_path) > 512 or any(ch in stream_path for ch in "\\r\\n"):
            raise ValueError("Invalid camera stream path")
        now = utc_now()
        with sqlite3.connect(self.path) as conn:
            cur = conn.execute(
                """INSERT INTO cameras
                   (name,host,port,protocol,username,audio_enabled,enabled,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,1,?,?)""",
                (name, host, port, protocol, username, int(bool(audio_enabled)), now, now),
            )
            camera_id = int(cur.lastrowid)
        return self.get(camera_id)

    def list(self) -> list[dict]:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM cameras ORDER BY id DESC").fetchall()
        return [self._public(dict(row)) for row in rows]

    def get(self, camera_id: int) -> dict | None:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM cameras WHERE id=?", (int(camera_id),)).fetchone()
        return self._public(dict(row)) if row else None

    def delete(self, camera_id: int) -> bool:
        with sqlite3.connect(self.path) as conn:
            cur = conn.execute("DELETE FROM cameras WHERE id=?", (int(camera_id),))
        return cur.rowcount > 0

    @staticmethod
    def _public(camera: dict) -> dict:
        camera = dict(camera)
        camera["audio_enabled"] = bool(camera["audio_enabled"])
        camera["enabled"] = bool(camera["enabled"])
        camera["credential_configured"] = bool(camera.get("username")) and validate_secret_reference(camera["id"])
        camera["connection"] = "READY_FOR_BROKER" if camera["credential_configured"] else "CREDENTIAL_REQUIRED"
        camera["stream"] = build_server_side_stream_reference(camera)
        return camera

class EventCorrelator:
    """Correlate independent RF/audio/video observations by timestamp only."""
    def __init__(self, window_ms: int = 1000):
        if int(window_ms) < 0 or int(window_ms) > 60000:
            raise ValueError("Correlation window must be 0..60000 ms")
        self.window_ms = int(window_ms)

    @staticmethod
    def _epoch_ms(timestamp: str) -> float:
        value = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.timestamp() * 1000.0

    def correlate(self, events: list[dict]) -> list[dict]:
        normalized = []
        for event in events:
            if not event.get("event_type") or not event.get("timestamp"):
                continue
            item = {
                "event_id": str(event.get("event_id", "")),
                "event_type": str(event["event_type"]),
                "source_id": str(event.get("source_id", "")),
                "source_type": str(event.get("source_type", "UNKNOWN")),
                "timestamp": str(event["timestamp"]),
                "payload": dict(event.get("payload") or {}),
            }
            item["_ts_ms"] = self._epoch_ms(item["timestamp"])
            normalized.append(item)
        groups, used = [], set()
        for i, anchor in enumerate(normalized):
            if i in used:
                continue
            group = [anchor]; used.add(i)
            for j, candidate in enumerate(normalized):
                if j in used:
                    continue
                if abs(candidate["_ts_ms"] - anchor["_ts_ms"]) <= self.window_ms:
                    group.append(candidate); used.add(j)
            if len(group) > 1:
                group_id = f"corr-{i+1:04d}"
                for item in group:
                    item["correlation_group_id"] = group_id
                    item.pop("_ts_ms", None)
                groups.append({
                    "correlation_group_id": group_id,
                    "window_ms": self.window_ms,
                    "events": group,
                    "interpretation": "Temporal correlation only; not causal attribution.",
                })
        return groups


class VisionEventStore:
    """Persist camera/video/audio observations without turning them into RF measurements."""
    def __init__(self, database_path: str, max_payload_bytes: int = 16384):
        self.path = Path(database_path)
        self.max_payload_bytes = max_payload_bytes
        with sqlite3.connect(self.path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS vision_events (
                event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL, source_id TEXT NOT NULL,
                source_type TEXT NOT NULL, timestamp TEXT NOT NULL, payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )""")

    def add(self, event: dict) -> dict:
        required = ("event_id", "event_type", "source_id", "source_type", "timestamp")
        if any(not str(event.get(k, "")).strip() for k in required):
            raise ValueError("Vision event requires event_id, event_type, source_id, source_type and timestamp")
        source_type = str(event["source_type"]).upper()
        if source_type not in {"CAMERA_VIDEO", "CAMERA_AUDIO", "CAMERA_STATUS"}:
            raise ValueError("Vision event source_type must be CAMERA_VIDEO, CAMERA_AUDIO or CAMERA_STATUS")
        payload = dict(event.get("payload") or {})
        import json
        encoded = json.dumps(payload, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > self.max_payload_bytes:
            raise ValueError("Vision event payload is too large")
        item = {k: str(event[k]) for k in required}
        item["source_type"] = source_type
        item["payload"] = payload
        with sqlite3.connect(self.path) as conn:
            conn.execute("INSERT OR REPLACE INTO vision_events(event_id,event_type,source_id,source_type,timestamp,payload_json,created_at) VALUES(?,?,?,?,?,?,?)",
                         (item["event_id"], item["event_type"], item["source_id"], source_type, item["timestamp"], encoded, utc_now()))
        return item

    def recent(self, limit: int = 200) -> list[dict]:
        import json
        limit = max(1, min(1000, int(limit)))
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM vision_events ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
        return [{"event_id":r["event_id"],"event_type":r["event_type"],"source_id":r["source_id"],
                 "source_type":r["source_type"],"timestamp":r["timestamp"],"payload":json.loads(r["payload_json"])} for r in rows]

def camera_status(camera: dict) -> dict:
    if not camera:
        return {"state": "NOT_FOUND"}
    if not camera.get("enabled"):
        return {"state": "DISABLED"}
    if not camera.get("credential_configured"):
        return {"state": "CREDENTIAL_REQUIRED"}
    return {
        "state": "READY_FOR_BROKER",
        "stream": camera["stream"],
        "message": "Camera metadata is configured. Start the backend broker to expose browser playback.",
    }
