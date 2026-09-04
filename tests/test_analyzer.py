"""Unit tests for the FFT spectrum analyzer."""

import numpy as np

from app.config import Config
from app.dsp.analyzer import SpectrumAnalyzer


class TestSpectrumAnalyzer:
    def setup_method(self):
        self.config = Config(fft_size=2048, sample_rate=2_000_000, center_frequency=100_000_000)
        self.analyzer = SpectrumAnalyzer(self.config)

    def test_frequency_resolution(self):
        expected_res = self.config.sample_rate / self.config.fft_size
        assert abs(self.analyzer.get_frequency_resolution() - expected_res) < 1e-6

    def test_analyze_returns_correct_shapes(self):
        iq_data = np.random.randn(self.config.fft_size) + 1j * np.random.randn(self.config.fft_size)
        frequencies, power_spectrum, noise_floor = self.analyzer.analyze(iq_data)
        assert frequencies.shape == (self.config.fft_size,)
        assert power_spectrum.shape == (self.config.fft_size,)
        assert isinstance(noise_floor, (float, np.floating))

    def test_analyze_output_types(self):
        iq_data = np.random.randn(self.config.fft_size) + 1j * np.random.randn(self.config.fft_size)
        frequencies, power_spectrum, noise_floor = self.analyzer.analyze(iq_data)
        assert isinstance(frequencies, np.ndarray)
        assert isinstance(power_spectrum, np.ndarray)
        assert np.isfinite(noise_floor)

    def test_noise_floor_estimation(self):
        """Noise floor should be a robust central estimate, not the absolute minimum."""
        rng = np.random.default_rng(1234)
        iq_data = rng.standard_normal(self.config.fft_size) + 1j * rng.standard_normal(self.config.fft_size)
        _, power_spectrum, noise_floor = self.analyzer.analyze(iq_data)
        assert np.isclose(noise_floor, np.median(power_spectrum))
        assert noise_floor < np.max(power_spectrum)

    def test_analyze_dc_signal(self):
        iq_data = np.ones(self.config.fft_size, dtype=complex)
        frequencies, power_spectrum, noise_floor = self.analyzer.analyze(iq_data)
        center_idx = self.config.fft_size // 2
        assert power_spectrum[center_idx] > noise_floor + 10
        assert abs(frequencies[center_idx] - self.config.center_frequency) < self.analyzer.get_frequency_resolution()
