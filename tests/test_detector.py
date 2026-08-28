"""Unit tests for the RF signal detector."""

import pytest
import numpy as np
from app.config import Config
from app.dsp.analyzer import SpectrumAnalyzer
from app.dsp.detector import SignalDetector, Detection


class TestSignalDetector:
    """Test suite for SignalDetector."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = Config(
            fft_size=2048,
            sample_rate=2_000_000,
            center_frequency=100_000_000,
            detection_threshold_db=6.0,
            minimum_signal_bandwidth_hz=10_000
        )
        self.detector = SignalDetector(self.config)
        self.analyzer = SpectrumAnalyzer(self.config)
    
    def test_detection_initialization(self):
        """Test detector initializes correctly."""
        assert self.detector.config.detection_threshold_db == 6.0
    
    def test_detect_no_signals(self):
        """Test detection with no signals (just noise)."""
        # Pure noise
        iq_data = np.random.randn(self.config.fft_size) + \
                  1j * np.random.randn(self.config.fft_size)
        frequencies, power_spectrum, noise_floor = self.analyzer.analyze(iq_data)
        
        detections = self.detector.detect(frequencies, power_spectrum, noise_floor)
        
        # Should detect very few or no signals
        assert len(detections) == 0
    
    def test_detect_strong_signal(self):
        """Test detection of a strong signal."""
        # Create a strong signal
        t = np.arange(self.config.fft_size) / self.config.sample_rate
        signal_freq = self.config.center_frequency
        signal = 0.5 * np.exp(2j * np.pi * signal_freq * t)
        noise = 0.01 * (np.random.randn(self.config.fft_size) + \
                        1j * np.random.randn(self.config.fft_size))
        iq_data = signal + noise
        
        frequencies, power_spectrum, noise_floor = self.analyzer.analyze(iq_data)
        detections = self.detector.detect(frequencies, power_spectrum, noise_floor)
        
        # Should detect at least one signal
        assert len(detections) >= 1
        # First detection should be near center frequency
        assert abs(detections[0].center_frequency_hz - self.config.center_frequency) < 100_000
    
    def test_detection_attributes(self):
        """Test that Detection objects have correct attributes."""
        detection = Detection(
            center_frequency_hz=100_000_000,
            peak_power_db=-20.0,
            noise_floor_db=-80.0,
            snr_db=60.0,
            bandwidth_hz=50_000,
            peak_magnitude=0.1,
            timestamp_frame=1
        )
        
        assert detection.center_frequency_hz == 100_000_000
        assert detection.peak_power_db == -20.0
        assert detection.snr_db == 60.0
        assert detection.bandwidth_hz == 50_000
        assert detection.timestamp_frame == 1
