"""FFT-based Spectrum Analyzer."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Tuple

import numpy as np
from scipy import signal

from app.source_types import SourceType, normalize_source_type


class SpectrumAnalyzer:
    """Performs FFT-based spectrum analysis on complex baseband IQ samples."""

    def __init__(self, config):
        self.config = config
        self.window = signal.windows.hamming(config.fft_size)

    def analyze(self, iq_data: np.ndarray) -> Tuple[np.ndarray, np.ndarray, float]:
        """Analyze exactly one FFT frame and return frequencies, dBFS power, noise floor."""
        iq_data = np.asarray(iq_data, dtype=np.complex128).reshape(-1)
        if iq_data.size != self.config.fft_size:
            raise ValueError(
                f"Expected {self.config.fft_size} IQ samples, got {iq_data.size}"
            )
        if not np.all(np.isfinite(iq_data.real)) or not np.all(np.isfinite(iq_data.imag)):
            raise ValueError("IQ data must contain only finite values")

        windowed = iq_data * self.window
        fft_shifted = np.fft.fftshift(np.fft.fft(windowed))

        # With normalized complex IQ, 0 dBFS corresponds to a unit-amplitude
        # single-bin complex tone. Window coherent gain keeps the tone reference
        # stable; this remains a relative digital full-scale measurement, not RF
        # dBm calibration.
        coherent_gain = float(np.sum(self.window) / self.config.fft_size)
        power_linear = (np.abs(fft_shifted) / (self.config.fft_size * coherent_gain)) ** 2
        power_dbfs = 10.0 * np.log10(np.maximum(power_linear, np.finfo(float).tiny))

        # fftshift(fftfreq(N)) is ordered from -Fs/2 to Fs/2-Fs/N. The upper
        # Nyquist endpoint is not a distinct FFT bin for even N.
        freq_bins = np.fft.fftshift(
            np.fft.fftfreq(self.config.fft_size, d=1.0 / self.config.sample_rate)
        )
        frequencies = self.config.center_frequency + freq_bins
        noise_floor = float(np.median(power_dbfs))
        return frequencies, power_dbfs, noise_floor

    def analyze_frame(
        self,
        iq_data: np.ndarray,
        source_type: SourceType | str,
        timestamp: str | None = None,
    ) -> dict:
        """Return a serializable, source-aware spectrum frame."""
        normalized_source = normalize_source_type(source_type)
        frequencies, power_dbfs, noise_floor = self.analyze(iq_data)
        return {
            "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
            "frequencies_hz": [float(x) for x in frequencies],
            "power_dbfs": [float(x) for x in power_dbfs],
            "noise_floor_dbfs": float(noise_floor),
            "center_frequency_hz": float(self.config.center_frequency),
            "sample_rate_hz": float(self.config.sample_rate),
            "fft_size": int(self.config.fft_size),
            "source_type": normalized_source.value,
            "frequency_start_hz": float(self.config.center_frequency - self.config.sample_rate / 2),
            "frequency_end_hz": float(self.config.center_frequency + self.config.sample_rate / 2),
            "frequency_resolution_hz": self.get_frequency_resolution(),
        }

    def get_frequency_resolution(self) -> float:
        """Return the FFT bin spacing in Hz."""
        return self.config.sample_rate / self.config.fft_size
