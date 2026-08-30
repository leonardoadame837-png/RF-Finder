"""Optional RTL-SDR source.

The driver is imported lazily so RF Finder remains installable and testable
without SDR hardware. Physical device control should only be called from an
authorized operator/admin service boundary.
"""
from __future__ import annotations

import numpy as np

from .base import SampleSource


class RtlSdrSource(SampleSource):
    def __init__(self, sample_rate: int, center_frequency: int, gain: float | str = "auto", device_index: int = 0, frame_size: int = 2048):
        self.sample_rate = sample_rate
        self.center_frequency = center_frequency
        self.gain = gain
        self.device_index = device_index
        self.frame_size = frame_size
        self._sdr = None

    def start(self) -> None:
        try:
            from rtlsdr import RtlSdr
        except ImportError as exc:
            raise RuntimeError("RTL-SDR support requires the optional 'pyrtlsdr' package and compatible driver") from exc
        self._sdr = RtlSdr(self.device_index)
        self._sdr.sample_rate = self.sample_rate
        self._sdr.center_freq = self.center_frequency
        self._sdr.gain = self.gain

    def stop(self) -> None:
        if self._sdr is not None:
            self._sdr.close()
            self._sdr = None

    def generate_frame(self) -> np.ndarray:
        if self._sdr is None:
            raise RuntimeError("RTL-SDR source is not started")
        return np.asarray(self._sdr.read_samples(self.frame_size), dtype=np.complex64)

    def device_info(self) -> dict:
        return {
            "driver": "rtl-sdr",
            "device_index": self.device_index,
            "sample_rate_hz": self.sample_rate,
            "center_frequency_hz": self.center_frequency,
        }
