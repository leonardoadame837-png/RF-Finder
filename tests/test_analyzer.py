"""Unit tests for the FFT spectrum analyzer."""

import pytest
import numpy as np
from app.config import Config
from app.dsp.analyzer import SpectrumAnalyzer


class TestSpectrumAnalyzer:
    """Test suite for SpectrumAnalyzer."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = Config(fft_size=2048, sample_rate=2_000_000, center_frequency=100_000_000)
        self.analyzer = SpectrumAnalyzer(self.config)
    
    def test_frequency_resolution(self):
        """Test frequency resolution calculation."""
        expected_res = self.config.sample_rate / self.config.fft_size
        actual_res = self.analyzer.get_frequency_resolution()
        assert abs(actual_res - expected_res) < 1e-6
    
    def test_analyze_returns_correct_shapes(self):
        """Test that analyze returns arrays of correct shape."""
        iq_data = np.random.randn(self.config.fft_size) + \
                  1j * np.random.randn(self.config.fft_size)
        frequencies, power_spectrum, noise_floor = self.analyzer.analyze(iq_data)
        
        assert frequencies.shape == (self.config.fft_size,)
        assert power_spectrum.shape == (self.config.fft_size,)
        assert isinstance(noise_floor, (float, np.floating))
    
    def test_analyze_output_types(self):
        """Test that analyze returns correct data types."""
        iq_data = np.random.randn(self.config.fft_size) + \
                  1j * np.random.randn(self.config.fft_size)
        frequencies, power_spectrum, noise_floor = self.analyzer.analyze(iq_data)
        
        assert isinstance(frequencies, np.ndarray)
        assert isinstance(power_spectrum, np.ndarray)
        assert np.isfinite(noise_floor)
    
    def test_noise_floor_estimation(self):
        """Test that noise floor is estimated as reasonable percentile."""
        iq_data = np.random.randn(self.config.fft_size) + \
                  1j * np.random.randn(self.config.fft_size)
        frequencies, power_spectrum, noise_floor = self.analyzer.analyze(iq_data)
        
        # Noise floor should be below minimum power spectrum
        assert noise_floor < np.min(power_spectrum)
    
    def test_analyze_dc_signal(self):
        """Test analyzing a pure DC signal (no modulation)."""
        iq_data = np.ones(self.config.fft_size, dtype=complex)
        frequencies, power_spectrum, noise_floor = self.analyzer.analyze(iq_data)
        
        # Should have peak at DC (center of FFT)
        center_idx = self.config.fft_size // 2
        assert power_spectrum[center_idx] > noise_floor + 10  # Strong peak
