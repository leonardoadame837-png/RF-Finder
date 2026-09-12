"""Optional receive-only SDR capture source."""

from __future__ import annotations

import numpy as np

from app.source_types import SourceType


class SDRUnavailableError(RuntimeError):
    """Raised when the optional SDR backend cannot be used."""


class RTLSDRSource:
    """Receive-only RTL-SDR source using the optional ``pyrtlsdr`` package."""

    def __init__(self, config, device_index: int = 0, gain: str | float = "auto"):
        self.config = config
        self.device_index = device_index
        self.gain = gain
        self.frame_index = 0
        self.running = False
        self._sdr = None

    def start(self) -> None:
        if self.running:
            return
        try:
            from rtlsdr import RtlSdr
        except ImportError as exc:
            raise SDRUnavailableError("RTL-SDR support is optional. Install pyrtlsdr and the native RTL-SDR driver before selecting --source sdr.") from exc
        try:
            self._sdr = RtlSdr(self.device_index)
            self._sdr.sample_rate = self.config.sample_rate
            self._sdr.center_freq = self.config.center_frequency
            self._sdr.gain = "auto" if self.gain == "auto" else float(self.gain)
        except Exception as exc:
            self._close_device()
            raise SDRUnavailableError(f"Unable to open RTL-SDR device: {exc}") from exc
        self.frame_index = 0
        self.running = True

    def stop(self) -> None:
        self.running = False
        self._close_device()
        self.frame_index = 0

    def _close_device(self) -> None:
        if self._sdr is not None:
            try:
                self._sdr.close()
            except Exception:
                pass
            self._sdr = None

    def generate_frame(self) -> np.ndarray:
        if not self.running or self._sdr is None:
            raise RuntimeError("SDR source is not running")
        samples = np.asarray(self._sdr.read_samples(self.config.fft_size), dtype=np.complex128)
        if samples.size != self.config.fft_size:
            raise RuntimeError(f"SDR returned {samples.size} samples; expected {self.config.fft_size}")
        self.frame_index += 1
        return samples

    def status(self) -> dict:
        return {"active": self.running, "source": "sdr", "source_type": SourceType.LIVE_MEASUREMENT.value, "backend": "rtl-sdr", "device_index": self.device_index, "sample_rate_hz": self.config.sample_rate, "center_frequency_hz": self.config.center_frequency, "gain": self.gain, "frame_index": self.frame_index}
