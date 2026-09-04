"""FFT-based Spectrum Analyzer."""

from typing import Tuple

import numpy as np
from scipy import signal


class SpectrumAnalyzer:
    """Performs FFT-based spectrum analysis on RF signals."""

    def __init__(self, config):
        self.config = config
        self.window = signal.windows.hamming(config.fft_size)

    def analyze(self, iq_data: np.ndarray) -> Tuple[np.ndarray, np.ndarray, float]:
        """Analyze complex IQ samples and return frequencies, power, and noise floor."""
        iq_data = np.asarray(iq_data)
        if iq_data.size != self.config.fft_size:
            raise ValueError(
                f"Expected {self.config.fft_size} IQ samples, got {iq_data.size}"
            )
        if not np.all(np.isfinite(iq_data.real)) or not np.all(np.isfinite(iq_data.imag)):
            raise ValueError("IQ data must contain only finite values")

        windowed = iq_data * self.window
        fft_shifted = np.fft.fftshift(np.fft.fft(windowed))
        magnitude = np.abs(fft_shifted)

        # Power spectral density-like scale. The absolute reference is not an
        # RF calibration; it is used consistently for relative detection/SNR.
        power_linear = (magnitude ** 2) / self.config.fft_size
        power_db = 10.0 * np.log10(power_linear + np.finfo(float).tiny)

        # FFT bins are exact and do not include the upper Nyquist endpoint.
        freq_bins = np.fft.fftshift(
            np.fft.fftfreq(self.config.fft_size, d=1.0 / self.config.sample_rate)
        )
        frequencies = self.config.center_frequency + freq_bins

        # Median power is a robust baseline for broadband noise and is much less
        # sensitive to the random low-tail of an FFT than a 5th percentile.
        noise_floor = float(np.median(power_db))
        return frequencies, power_db, noise_floor

    def get_frequency_resolution(self) -> float:
        """Return the FFT bin spacing in Hz."""
        return self.config.sample_rate / self.config.fft_size
