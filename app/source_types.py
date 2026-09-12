"""Explicit provenance types for every RF spectrum frame and detection."""

from enum import Enum


class SourceType(str, Enum):
    SIMULATED = "SIMULATED"
    IMPORTED_MEASUREMENT = "IMPORTED_MEASUREMENT"
    LIVE_MEASUREMENT = "LIVE_MEASUREMENT"
    UNKNOWN = "UNKNOWN"

    @property
    def is_measurement(self) -> bool:
        return self in {SourceType.IMPORTED_MEASUREMENT, SourceType.LIVE_MEASUREMENT}


def normalize_source_type(value: object) -> SourceType:
    """Normalize legacy source labels without ever upgrading simulation to measurement."""
    if isinstance(value, SourceType):
        return value
    text = str(value or "UNKNOWN").strip().upper()
    aliases = {
        "SIMULATOR": SourceType.SIMULATED,
        "SIMULATION": SourceType.SIMULATED,
        "SYNTHETIC": SourceType.SIMULATED,
        "SDR": SourceType.LIVE_MEASUREMENT,
        "LIVE": SourceType.LIVE_MEASUREMENT,
        "MEASURED": SourceType.LIVE_MEASUREMENT,
        "IMPORTED": SourceType.IMPORTED_MEASUREMENT,
        "IMPORT": SourceType.IMPORTED_MEASUREMENT,
        "UNKNOWN": SourceType.UNKNOWN,
    }
    return aliases.get(text, SourceType.UNKNOWN)
