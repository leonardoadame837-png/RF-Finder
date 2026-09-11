"""Device telemetry model shared by phone, laptop, and desktop clients."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone


@dataclass
class DeviceTelemetry:
    """Optional client telemetry; it never masquerades as RF measurements."""

    platform: str = "unknown"
    client: str = "unknown"
    latitude: float | None = None
    longitude: float | None = None
    accuracy_m: float | None = None
    altitude_m: float | None = None
    heading_deg: float | None = None
    acceleration_x: float | None = None
    acceleration_y: float | None = None
    acceleration_z: float | None = None
    rotation_alpha: float | None = None
    rotation_beta: float | None = None
    rotation_gamma: float | None = None
    updated_at: str | None = None

    def update(self, **values) -> None:
        for key, value in values.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def as_dict(self) -> dict:
        return asdict(self)


class TelemetryStore:
    """Thread-safe-in-practice latest telemetry container for one local service."""

    def __init__(self):
        self._telemetry = DeviceTelemetry()

    def update(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("telemetry payload must be an object")
        self._telemetry.update(**payload)
        return self._telemetry.as_dict()

    def current(self) -> dict:
        return self._telemetry.as_dict()
