"""Cross-platform capture-source contract and provenance helpers."""

from __future__ import annotations

from typing import Protocol

import numpy as np

from app.sources.types import SourceType, normalize_source_type


class CaptureSource(Protocol):
    """Minimal contract required by the RF processing service."""

    frame_index: int

    def start(self) -> None: ...
    def stop(self) -> None: ...
    def generate_frame(self) -> np.ndarray: ...
    def status(self) -> dict: ...


# Legacy names remain accepted by existing source implementations.
SOURCE_MODES = ("simulator", "sdr", "imported")


def source_provenance(source: CaptureSource) -> dict:
    """Return source-aware provenance without guessing that data is verified."""
    status = source.status() if hasattr(source, "status") else {}
    raw_name = str(status.get("source", "unknown"))
    source_type = normalize_source_type(raw_name)
    return {
        # Keep legacy field for existing consumers.
        "source": raw_name.lower(),
        "source_type": source_type.value,
        "verified_rf": source_type in {
            SourceType.IMPORTED_MEASUREMENT,
            SourceType.LIVE_MEASUREMENT,
        },
        "simulated": source_type is SourceType.SIMULATED,
        "capture_kind": (
            "synthetic_iq" if source_type is SourceType.SIMULATED
            else "imported_iq" if source_type is SourceType.IMPORTED_MEASUREMENT
            else "hardware_iq" if source_type is SourceType.LIVE_MEASUREMENT
            else "unknown"
        ),
    }
