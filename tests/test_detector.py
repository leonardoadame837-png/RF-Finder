"""Unit tests for the RF signal detector."""

import numpy as np

from app.config import Config
from app.dsp.analyzer import SpectrumAnalyzer
from app.dsp.detector import Detection, SignalDetector


class TestSignalDetector:
    def setup_method(self):
        self.config = Config(
            fft_size=2048,
            sample_rate=2_000_000,
            center_frequency=100_000_000,
            detection_threshold_db=6.0,
            minimum_signal_bandwidth_hz=500,
        )
        self.detector = SignalDetector(self.config)
        self.analyzer = SpectrumAnalyzer(self.config)

    def test_detection_initialization(self):
        assert self.detector.config.detection_threshold_db == 6.0

    def test_detect_no_signals(self):
        iq_data = np.random.randn(self.config.fft_size) + 1j * np.random.randn(self.config.fft_size)
        frequencies, power_spectrum, noise_floor = self.analyzer.analyze(iq_data)
        detections = self.detector.detect(frequencies, power_spectrum, noise_floor)
        assert len(detections) == 0

    def test_detect_strong_signal(self):
        t = np.arange(self.config.fft_size) / self.config.sample_rate
        signal = 0.5 * np.exp(2j * np.pi * 0 * t)
        noise = 0.01 * (np.random.randn(self.config.fft_size) + 1j * np.random.randn(self.config.fft_size))
        frequencies, power_spectrum, noise_floor = self.analyzer.analyze(signal + noise)
        detections = self.detector.detect(frequencies, power_spectrum, noise_floor)
        assert len(detections) >= 1
        assert abs(detections[0].center_frequency_hz - self.config.center_frequency) < 100_000

    def test_detection_attributes(self):
        detection = Detection(
            center_frequency_hz=100_000_000,
            peak_power_db=-20.0,
            noise_floor_db=-80.0,
            snr_db=60.0,
            bandwidth_hz=50_000,
            peak_magnitude=0.1,
            timestamp_frame=1,
        )
        assert detection.center_frequency_hz == 100_000_000
        assert detection.peak_power_db == -20.0
        assert detection.snr_db == 60.0
        assert detection.bandwidth_hz == 50_000
        assert detection.timestamp_frame == 1
