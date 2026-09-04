"""Unit tests for frequency axis validation."""

import numpy as np

from app.config import Config
from app.dsp.analyzer import SpectrumAnalyzer


class TestFrequencyAxis:
    def setup_method(self):
        self.config = Config(fft_size=2048, sample_rate=2_000_000, center_frequency=100_000_000)
        self.analyzer = SpectrumAnalyzer(self.config)

    def test_frequency_axis_is_monotonic_increasing(self):
        iq_data = np.random.randn(self.config.fft_size) + 1j * np.random.randn(self.config.fft_size)
        frequencies, _, _ = self.analyzer.analyze(iq_data)
        assert np.all(np.diff(frequencies) > 0)

    def test_frequency_axis_range(self):
        iq_data = np.random.randn(self.config.fft_size) + 1j * np.random.randn(self.config.fft_size)
        frequencies, _, _ = self.analyzer.analyze(iq_data)
        expected_min = self.config.center_frequency - self.config.sample_rate / 2
        expected_max = self.config.center_frequency + self.config.sample_rate / 2
        resolution = self.analyzer.get_frequency_resolution()
        assert abs(frequencies[0] - expected_min) < resolution
        # FFT frequency bins form a half-open interval: the last bin is one
        # resolution below center + sample_rate/2.
        assert abs(frequencies[-1] - (expected_max - resolution)) < resolution * 1e-9

    def test_frequency_axis_contains_center_frequency(self):
        iq_data = np.random.randn(self.config.fft_size) + 1j * np.random.randn(self.config.fft_size)
        frequencies, _, _ = self.analyzer.analyze(iq_data)
        nearest_freq = frequencies[np.argmin(np.abs(frequencies - self.config.center_frequency))]
        assert abs(nearest_freq - self.config.center_frequency) < self.analyzer.get_frequency_resolution()

    def test_frequency_bin_spacing(self):
        iq_data = np.random.randn(self.config.fft_size) + 1j * np.random.randn(self.config.fft_size)
        frequencies, _, _ = self.analyzer.analyze(iq_data)
        expected_res = self.analyzer.get_frequency_resolution()
        assert np.allclose(np.diff(frequencies), expected_res, rtol=1e-9, atol=1e-9)

    def test_frequency_axis_length(self):
        iq_data = np.random.randn(self.config.fft_size) + 1j * np.random.randn(self.config.fft_size)
        frequencies, power_spectrum, _ = self.analyzer.analyze(iq_data)
        assert len(frequencies) == self.config.fft_size
        assert len(power_spectrum) == self.config.fft_size
        assert len(frequencies) == len(power_spectrum)

    def test_dc_component_location(self):
        iq_data = np.ones(self.config.fft_size, dtype=complex)
        frequencies, power_spectrum, _ = self.analyzer.analyze(iq_data)
        center_idx = np.argmin(np.abs(frequencies - self.config.center_frequency))
        peak_idx = np.argmax(power_spectrum)
        assert abs(peak_idx - center_idx) < 3
