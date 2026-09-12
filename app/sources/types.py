"""Source provenance types shared by capture frames, spectra, and detections."""

from enum import StrEnum


class SourceType(StrEnum):
    SIMULATED = "SIMULATED"
    IMPORTED_MEASUREMENT = "IMPORTED_MEASUREMENT"
    LIVE_MEASUREMENT = "LIVE_MEASUREMENT"
    UNKNOWN = "UNKNOWN"


VERIFIED_SOURCE_TYPES = frozenset({
    SourceType.IMPORTED_MEASUREMENT,
    SourceType.LIVE_MEASUREMENT,
})


def normalize_source_type(value: object) -> SourceType:
    """Normalize legacy source names without treating them as verified measurements."""
    if isinstance(value, SourceType):
        return value
    normalized = str(value or "").strip().upper()
    aliases = {
        "SIMULATOR": SourceType.SIMULATED,
        "SIMULATION": SourceType.SIMULATED,
        "SDR": SourceType.LIVE_MEASUREMENT,
        "LIVE": SourceType.LIVE_MEASUREMENT,
        "MEASURED": SourceType.LIVE_MEASUREMENT,
        "IMPORTED": SourceType.IMPORTED_MEASUREMENT,
        "IMPORT": SourceType.IMPORTED_MEASUREMENT,
    }
    return aliases.get(normalized, SourceType.UNKNOWN)


def is_verified_measurement(source_type: SourceType | str) -> bool:
    return normalize_source_type(source_type) in VERIFIED_SOURCE_TYPES
