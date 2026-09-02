"""Unit tests for frequency axis validation."""

import pytest
import numpy as np
from app.config import Config
from app.dsp.analyzer import SpectrumAnalyzer


class TestFrequencyAxis:
    """Test suite for frequency axis ordering and correctness."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = Config(fft_size=2048, sample_rate=2_000_000, center_frequency=100_000_000)
        self.analyzer = SpectrumAnalyzer(self.config)
    
    def test_frequency_axis_is_monotonic_increasing(self):
        """Test that frequency axis is monotonically increasing."""
        iq_data = np.random.randn(self.config.fft_size) + 1j * np.random.randn(self.config.fft_size)
        frequencies, _, _ = self.analyzer.analyze(iq_data)
        
        # Check monotonically increasing
        assert np.all(np.diff(frequencies) > 0), "Frequency axis should be monotonically increasing"
    
    def test_frequency_axis_range(self):
        """Test that frequency axis spans correct range around center frequency."""
        iq_data = np.random.randn(self.config.fft_size) + 1j * np.random.randn(self.config.fft_size)
        frequencies, _, _ = self.analyzer.analyze(iq_data)
        
        # Expected range: center_freq - sample_rate/2 to center_freq + sample_rate/2
        expected_min = self.config.center_frequency - self.config.sample_rate / 2
        expected_max = self.config.center_frequency + self.config.sample_rate / 2
        
        actual_min = frequencies[0]
        actual_max = frequencies[-1]
        
        print(f"\nExpected range: [{expected_min:.0f}, {expected_max:.0f}]")
        print(f"Actual range:   [{actual_min:.0f}, {actual_max:.0f}]")
        
        # Allow small tolerance due to FFT binning
        tolerance = self.config.sample_rate / self.config.fft_size  # 1 bin
        assert abs(actual_min - expected_min) < tolerance, f"Min frequency mismatch: {actual_min} vs {expected_min}"
        assert abs(actual_max - expected_max) < tolerance, f"Max frequency mismatch: {actual_max} vs {expected_max}"
    
    def test_frequency_axis_contains_center_frequency(self):
        """Test that center frequency is within the frequency axis."""
        iq_data = np.random.randn(self.config.fft_size) + 1j * np.random.randn(self.config.fft_size)
        frequencies, _, _ = self.analyzer.analyze(iq_data)
        
        # Find nearest frequency to center
        nearest_freq = frequencies[np.argmin(np.abs(frequencies - self.config.center_frequency))]
        
        freq_res = self.analyzer.get_frequency_resolution()
        print(f"\nCenter frequency: {self.config.center_frequency}")
        print(f"Nearest bin:      {nearest_freq}")
        print(f"Frequency resolution: {freq_res}")
        
        assert abs(nearest_freq - self.config.center_frequency) < freq_res, \
            "Center frequency should be representable in frequency axis"
    
    def test_frequency_bin_spacing(self):
        """Test that frequency bins are evenly spaced by frequency resolution."""
        iq_data = np.random.randn(self.config.fft_size) + 1j * np.random.randn(self.config.fft_size)
        frequencies, _, _ = self.analyzer.analyze(iq_data)
        
        expected_res = self.analyzer.get_frequency_resolution()
        actual_diffs = np.diff(frequencies)
        
        print(f"\nExpected bin spacing: {expected_res}")
        print(f"Actual bin spacing (min/max): {np.min(actual_diffs)} / {np.max(actual_diffs)}")
        
        # All differences should be equal to frequency resolution
        assert np.allclose(actual_diffs, expected_res, rtol=1e-9), \
            "Frequency bins should be evenly spaced"
    
    def test_frequency_axis_length(self):
        """Test that frequency axis matches FFT size."""
        iq_data = np.random.randn(self.config.fft_size) + 1j * np.random.randn(self.config.fft_size)
        frequencies, power_spectrum, _ = self.analyzer.analyze(iq_data)
        
        assert len(frequencies) == self.config.fft_size, \
            f"Frequency axis length {len(frequencies)} should match FFT size {self.config.fft_size}"
        assert len(power_spectrum) == self.config.fft_size, \
            f"Power spectrum length {len(power_spectrum)} should match FFT size {self.config.fft_size}"
        assert len(frequencies) == len(power_spectrum), \
            "Frequency and power spectrum arrays should have same length"
    
    def test_dc_component_location(self):
        """Test that DC component (f=center_frequency) is locatable in frequency axis."""
        # Create signal with known frequency component at center frequency
        iq_data = np.ones(self.config.fft_size, dtype=complex)
        frequencies, power_spectrum, noise_floor = self.analyzer.analyze(iq_data)
        
        # DC signal should show peak near center frequency
        center_idx = np.argmin(np.abs(frequencies - self.config.center_frequency))
        peak_idx = np.argmax(power_spectrum)
        
        print(f"\nDC signal peak index: {peak_idx}")
        print(f"Center frequency index: {center_idx}")
        print(f"Peak frequency: {frequencies[peak_idx]}")
        print(f"Center frequency: {frequencies[center_idx]}")
        
        # Peak should be very close to center frequency
        assert abs(peak_idx - center_idx) < 3, \
            "DC peak should be near center frequency bin"
