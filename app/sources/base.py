"""Cross-platform capture-source contract for RF Finder.

A source supplies complex I/Q frames to the same DSP pipeline regardless of
whether RF Finder is running on Android, a laptop, or a desktop PC.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np


class CaptureSource(Protocol):
    """Minimal contract required by the RF processing service."""

    frame_index: int

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def generate_frame(self) -> np.ndarray: ...

    def status(self) -> dict: ...


SOURCE_MODES = ("simulator", "sdr")


def source_provenance(source: CaptureSource) -> dict:
    """Return normalized provenance without guessing that data is verified."""
    status = source.status() if hasattr(source, "status") else {}
    name = str(status.get("source", "unknown")).lower()
    return {
        "source": name,
        "verified_rf": name == "sdr",
        "simulated": name == "simulator",
        "capture_kind": "synthetic_iq" if name == "simulator" else "hardware_iq" if name == "sdr" else "unknown",
    }
