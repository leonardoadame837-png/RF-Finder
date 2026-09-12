"""Cross-platform capture-source contract for RF Finder."""

from __future__ import annotations

from typing import Protocol

import numpy as np

from app.source_types import SourceType, normalize_source_type


class CaptureSource(Protocol):
    frame_index: int
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def generate_frame(self) -> np.ndarray: ...
    def status(self) -> dict: ...


SOURCE_MODES = tuple(item.value for item in SourceType)


def source_provenance(source: CaptureSource) -> dict:
    """Return explicit provenance without upgrading unknown data to measurement."""
    status = source.status() if hasattr(source, "status") else {}
    raw_name = str(status.get("source", "unknown")).lower()
    source_type = normalize_source_type(status.get("source_type", raw_name))
    return {
        "source": raw_name,
        "source_type": source_type.value,
        "verified_rf": source_type.is_measurement,
        "simulated": source_type is SourceType.SIMULATED,
        "capture_kind": "synthetic_iq" if source_type is SourceType.SIMULATED else "imported_samples" if source_type is SourceType.IMPORTED_MEASUREMENT else "hardware_iq" if source_type is SourceType.LIVE_MEASUREMENT else "unknown",
    }
