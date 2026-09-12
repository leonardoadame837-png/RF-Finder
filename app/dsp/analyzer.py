"""FFT-based spectrum analyzer."""

from typing import Tuple

import numpy as np
from scipy import signal


class SpectrumAnalyzer:
    """Performs FFT-based spectrum analysis on complex baseband IQ."""

    def __init__(self, config):
        self.config = config
        self.window = signal.windows.hamming(config.fft_size)

    def analyze(self, iq_data: np.ndarray, *, center_frequency_hz: float | None = None,
                sample_rate_hz: float | None = None) -> Tuple[np.ndarray, np.ndarray, float]:
        """Return absolute frequency bins, dBFS-like power, and robust noise floor."""
        iq_data = np.asarray(iq_data)
        if iq_data.size != self.config.fft_size:
            raise ValueError(f"Expected {self.config.fft_size} IQ samples, got {iq_data.size}")
        if not np.all(np.isfinite(iq_data.real)) or not np.all(np.isfinite(iq_data.imag)):
            raise ValueError("IQ data must contain only finite values")

        sample_rate = float(self.config.sample_rate if sample_rate_hz is None else sample_rate_hz)
        center_frequency = float(self.config.center_frequency if center_frequency_hz is None else center_frequency_hz)
        if not np.isfinite(sample_rate) or sample_rate <= 0:
            raise ValueError("sample_rate_hz must be finite and positive")
        if not np.isfinite(center_frequency):
            raise ValueError("center_frequency_hz must be finite")

        windowed = iq_data * self.window
        fft_shifted = np.fft.fftshift(np.fft.fft(windowed))
        magnitude = np.abs(fft_shifted)
        power_linear = (magnitude ** 2) / self.config.fft_size
        power_db = 10.0 * np.log10(power_linear + np.finfo(float).tiny)

        freq_bins = np.fft.fftshift(np.fft.fftfreq(self.config.fft_size, d=1.0 / sample_rate))
        frequencies = center_frequency + freq_bins
        noise_floor = float(np.median(power_db))
        return frequencies, power_db, noise_floor

    def get_frequency_resolution(self) -> float:
        return self.config.sample_rate / self.config.fft_size
