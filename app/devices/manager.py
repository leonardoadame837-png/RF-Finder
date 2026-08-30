"""RF capture device registry and safe control boundary."""
from __future__ import annotations

from app.database.repositories import AuditRepository, DeviceRepository


class DeviceManager:
    def __init__(self, db):
        self.devices = DeviceRepository(db)
        self.audit = AuditRepository(db)

    def register(self, name: str, driver: str, serial: str | None = None, center_frequency_hz: float | None = None, sample_rate_hz: float | None = None) -> dict:
        device = self.devices.create(name, driver, serial, center_frequency_hz, sample_rate_hz)
        self.audit.record("device.register", resource="device", resource_id=device["id"])
        return device

    def list(self) -> list[dict]:
        return self.devices.list()

    def get(self, device_id: str) -> dict | None:
        return self.devices.get(device_id)
