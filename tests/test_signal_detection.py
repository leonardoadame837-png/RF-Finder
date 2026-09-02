"""Signal detection module with comprehensive tests."""

import numpy as np
from app.config import Config
from app.dsp.analyzer import SpectrumAnalyzer
from app.dsp.detector import SignalDetector
import pytest


class TestSignalDetection:
    """Test suite for signal detection functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = Config(fft_size=2048, sample_rate=2_000_000, 
                           center_frequency=100_000_000, 
                           detection_threshold_db=6.0)
        self.analyzer = SpectrumAnalyzer(self.config)
        self.detector = SignalDetector(self.config)
    
    def test_detect_signal_above_noise(self):
        """Test detection of a signal above noise floor."""
        # Create IQ data with noise + tone
        t = np.arange(self.config.fft_size) / self.config.sample_rate
        tone_freq = 5_000_000  # 5 MHz offset from center
        
        # Noise
        noise = (np.random.randn(self.config.fft_size) + 
                1j * np.random.randn(self.config.fft_size)) * 0.1
        
        # Signal at tone_freq relative to center
        signal = 0.5 * np.exp(2j * np.pi * tone_freq * t)
        iq_data = signal + noise
        
        frequencies, power_spectrum, noise_floor = self.analyzer.analyze(iq_data)
        detections = self.detector.detect(frequencies, power_spectrum, noise_floor)
        
        assert len(detections) > 0, "Should detect signal above noise"
        # Verify detection is near tone frequency
        detected_freq = detections[0].center_frequency_hz
        expected_freq = self.config.center_frequency + tone_freq
        assert abs(detected_freq - expected_freq) < 20_000, \
            f"Detection frequency {detected_freq} should be near {expected_freq}"
    
    def test_no_detection_in_noise(self):
        """Test no false detections in pure noise."""
        # Pure noise
        iq_data = ((np.random.randn(self.config.fft_size) + 
                   1j * np.random.randn(self.config.fft_size)) * 0.01)
        
        frequencies, power_spectrum, noise_floor = self.analyzer.analyze(iq_data)
        detections = self.detector.detect(frequencies, power_spectrum, noise_floor)
        
        assert len(detections) == 0, "Pure noise should not generate detections"
    
    def test_detection_snr_calculation(self):
        """Test SNR is calculated correctly."""
        t = np.arange(self.config.fft_size) / self.config.sample_rate
        tone_freq = 2_000_000
        
        noise = (np.random.randn(self.config.fft_size) + 
                1j * np.random.randn(self.config.fft_size)) * 0.1
        signal = 1.0 * np.exp(2j * np.pi * tone_freq * t)
        iq_data = signal + noise
        
        frequencies, power_spectrum, noise_floor = self.analyzer.analyze(iq_data)
        detections = self.detector.detect(frequencies, power_spectrum, noise_floor)
        
        assert len(detections) > 0
        det = detections[0]
        # SNR should be peak power minus noise floor
        expected_snr = det.peak_power_db - det.noise_floor_db
        assert abs(det.snr_db - expected_snr) < 0.1
    
    def test_multiple_signal_detection(self):
        """Test detection of multiple signals."""
        t = np.arange(self.config.fft_size) / self.config.sample_rate
        
        # Two tones
        freq1, freq2 = 1_000_000, 8_000_000
        signal1 = 0.5 * np.exp(2j * np.pi * freq1 * t)
        signal2 = 0.5 * np.exp(2j * np.pi * freq2 * t)
        noise = (np.random.randn(self.config.fft_size) + 
                1j * np.random.randn(self.config.fft_size)) * 0.1
        
        iq_data = signal1 + signal2 + noise
        
        frequencies, power_spectrum, noise_floor = self.analyzer.analyze(iq_data)
        detections = self.detector.detect(frequencies, power_spectrum, noise_floor)
        
        assert len(detections) >= 2, "Should detect both signals"
    
    def test_detection_with_minimum_bandwidth(self):
        """Test bandwidth filtering in detection."""
        # Very narrow signal (narrower than minimum_signal_bandwidth_hz)
        t = np.arange(self.config.fft_size) / self.config.sample_rate
        tone_freq = 3_000_000
        
        # Use low magnitude for narrow signal
        signal = 0.01 * np.exp(2j * np.pi * tone_freq * t)
        noise = (np.random.randn(self.config.fft_size) + 
                1j * np.random.randn(self.config.fft_size)) * 0.1
        
        iq_data = signal + noise
        frequencies, power_spectrum, noise_floor = self.analyzer.analyze(iq_data)
        detections = self.detector.detect(frequencies, power_spectrum, noise_floor)
        
        # Verify all detections meet minimum bandwidth
        for det in detections:
            assert det.bandwidth_hz >= self.config.minimum_signal_bandwidth_hz, \
                f"Detection bandwidth {det.bandwidth_hz} should be >= {self.config.minimum_signal_bandwidth_hz}"
    
    def test_detection_sorted_by_frequency(self):
        """Test that detections are sorted by frequency."""
        t = np.arange(self.config.fft_size) / self.config.sample_rate
        freqs = [1_000_000, 8_000_000, 4_000_000]  # Out of order
        
        signals = sum(0.5 * np.exp(2j * np.pi * f * t) for f in freqs)
        noise = (np.random.randn(self.config.fft_size) + 
                1j * np.random.randn(self.config.fft_size)) * 0.1
        
        iq_data = signals + noise
        frequencies, power_spectrum, noise_floor = self.analyzer.analyze(iq_data)
        detections = self.detector.detect(frequencies, power_spectrum, noise_floor)
        
        # Verify sorted
        if len(detections) > 1:
            for i in range(len(detections) - 1):
                assert detections[i].center_frequency_hz <= detections[i+1].center_frequency_hz


class TestEdgeCases:
    """Test edge cases in analyzer and detector."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = Config(fft_size=2048, sample_rate=2_000_000, center_frequency=100_000_000)
        self.analyzer = SpectrumAnalyzer(self.config)
        self.detector = SignalDetector(self.config)
    
    def test_analyzer_with_zero_input(self):
        """Test analyzer doesn't crash on zero input."""
        iq_data = np.zeros(self.config.fft_size, dtype=complex)
        frequencies, power_spectrum, noise_floor = self.analyzer.analyze(iq_data)
        
        assert frequencies.shape == (self.config.fft_size,)
        assert power_spectrum.shape == (self.config.fft_size,)
        assert np.isfinite(noise_floor)
    
    def test_analyzer_with_extreme_values(self):
        """Test analyzer handles extreme input values."""
        iq_data = np.ones(self.config.fft_size, dtype=complex) * 1e10
        frequencies, power_spectrum, noise_floor = self.analyzer.analyze(iq_data)
        
        assert np.all(np.isfinite(power_spectrum)), "Power spectrum should be finite"
        assert np.isfinite(noise_floor), "Noise floor should be finite"
    
    def test_analyzer_with_nan_handling(self):
        """Test analyzer is robust to NaN-adjacent inputs."""
        iq_data = np.random.randn(self.config.fft_size) + 1j * np.random.randn(self.config.fft_size)
        # Add a very small signal to avoid all-zero scenarios
        iq_data += 1e-10
        
        frequencies, power_spectrum, noise_floor = self.analyzer.analyze(iq_data)
        
        # Should not have NaN values
        assert np.all(np.isfinite(power_spectrum)), "Power spectrum contains NaN"
        assert np.isfinite(noise_floor), "Noise floor is NaN"
    
    def test_fft_size_variations(self):
        """Test analyzer works with different FFT sizes."""
        for fft_size in [512, 1024, 2048, 4096]:
            config = Config(fft_size=fft_size, sample_rate=2_000_000, center_frequency=100_000_000)
            analyzer = SpectrumAnalyzer(config)
            
            iq_data = np.random.randn(fft_size) + 1j * np.random.randn(fft_size)
            frequencies, power_spectrum, noise_floor = analyzer.analyze(iq_data)
            
            assert len(frequencies) == fft_size
            assert len(power_spectrum) == fft_size
    
    def test_sample_rate_variations(self):
        """Test analyzer works with different sample rates."""
        for sample_rate in [1_000_000, 2_000_000, 4_000_000]:
            config = Config(fft_size=2048, sample_rate=sample_rate, center_frequency=100_000_000)
            analyzer = SpectrumAnalyzer(config)
            
            iq_data = np.random.randn(2048) + 1j * np.random.randn(2048)
            frequencies, power_spectrum, noise_floor = analyzer.analyze(iq_data)
            
            freq_res = analyzer.get_frequency_resolution()
            expected_res = sample_rate / 2048
            assert abs(freq_res - expected_res) < 1e-6
