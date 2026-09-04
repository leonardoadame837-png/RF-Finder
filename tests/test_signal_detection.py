"""Signal detection tests using physically valid complex-baseband tones."""

import numpy as np

from app.config import Config
from app.dsp.analyzer import SpectrumAnalyzer
from app.dsp.detector import SignalDetector


class TestSignalDetection:
    def setup_method(self):
        self.config = Config(
            fft_size=2048,
            sample_rate=2_000_000,
            center_frequency=100_000_000,
            detection_threshold_db=6.0,
        )
        self.analyzer = SpectrumAnalyzer(self.config)
        self.detector = SignalDetector(self.config)

    def test_detect_signal_above_noise(self):
        t = np.arange(self.config.fft_size) / self.config.sample_rate
        tone_offset = 500_000
        noise = (np.random.randn(self.config.fft_size) + 1j * np.random.randn(self.config.fft_size)) * 0.01
        signal = 0.5 * np.exp(2j * np.pi * tone_offset * t)
        frequencies, power_spectrum, noise_floor = self.analyzer.analyze(signal + noise)
        detections = self.detector.detect(frequencies, power_spectrum, noise_floor)
        assert len(detections) > 0
        detected_freq = detections[0].center_frequency_hz
        expected_freq = self.config.center_frequency + tone_offset
        assert abs(detected_freq - expected_freq) < 20_000

    def test_no_detection_in_noise(self):
        iq_data = (np.random.randn(self.config.fft_size) + 1j * np.random.randn(self.config.fft_size)) * 0.01
        frequencies, power_spectrum, noise_floor = self.analyzer.analyze(iq_data)
        detections = self.detector.detect(frequencies, power_spectrum, noise_floor)
        assert len(detections) == 0

    def test_detection_snr_calculation(self):
        t = np.arange(self.config.fft_size) / self.config.sample_rate
        tone_offset = 250_000
        noise = (np.random.randn(self.config.fft_size) + 1j * np.random.randn(self.config.fft_size)) * 0.01
        signal = 1.0 * np.exp(2j * np.pi * tone_offset * t)
        frequencies, power_spectrum, noise_floor = self.analyzer.analyze(signal + noise)
        detections = self.detector.detect(frequencies, power_spectrum, noise_floor)
        assert len(detections) > 0
        det = detections[0]
        assert abs(det.snr_db - (det.peak_power_db - det.noise_floor_db)) < 0.1

    def test_multiple_signal_detection(self):
        t = np.arange(self.config.fft_size) / self.config.sample_rate
        offsets = [-700_000, 200_000]
        signals = sum(0.5 * np.exp(2j * np.pi * offset * t) for offset in offsets)
        noise = (np.random.randn(self.config.fft_size) + 1j * np.random.randn(self.config.fft_size)) * 0.01
        frequencies, power_spectrum, noise_floor = self.analyzer.analyze(signals + noise)
        detections = self.detector.detect(frequencies, power_spectrum, noise_floor)
        assert len(detections) >= 2

    def test_detection_with_minimum_bandwidth(self):
        t = np.arange(self.config.fft_size) / self.config.sample_rate
        tone_offset = 300_000
        signal = 0.01 * np.exp(2j * np.pi * tone_offset * t)
        noise = (np.random.randn(self.config.fft_size) + 1j * np.random.randn(self.config.fft_size)) * 0.1
        frequencies, power_spectrum, noise_floor = self.analyzer.analyze(signal + noise)
        detections = self.detector.detect(frequencies, power_spectrum, noise_floor)
        for det in detections:
            assert det.bandwidth_hz >= self.config.minimum_signal_bandwidth_hz

    def test_detection_sorted_by_frequency(self):
        t = np.arange(self.config.fft_size) / self.config.sample_rate
        offsets = [700_000, -300_000, 300_000]
        signals = sum(0.5 * np.exp(2j * np.pi * offset * t) for offset in offsets)
        noise = (np.random.randn(self.config.fft_size) + 1j * np.random.randn(self.config.fft_size)) * 0.01
        frequencies, power_spectrum, noise_floor = self.analyzer.analyze(signals + noise)
        detections = self.detector.detect(frequencies, power_spectrum, noise_floor)
        if len(detections) > 1:
            assert all(
                detections[i].center_frequency_hz <= detections[i + 1].center_frequency_hz
                for i in range(len(detections) - 1)
            )


class TestEdgeCases:
    def setup_method(self):
        self.config = Config(fft_size=2048, sample_rate=2_000_000, center_frequency=100_000_000)
        self.analyzer = SpectrumAnalyzer(self.config)

    def test_analyzer_with_zero_input(self):
        frequencies, power_spectrum, noise_floor = self.analyzer.analyze(
            np.zeros(self.config.fft_size, dtype=complex)
        )
        assert frequencies.shape == (self.config.fft_size,)
        assert power_spectrum.shape == (self.config.fft_size,)
        assert np.isfinite(noise_floor)

    def test_analyzer_with_extreme_values(self):
        _, power_spectrum, noise_floor = self.analyzer.analyze(
            np.ones(self.config.fft_size, dtype=complex) * 1e10
        )
        assert np.all(np.isfinite(power_spectrum))
        assert np.isfinite(noise_floor)

    def test_analyzer_with_nan_handling(self):
        iq_data = np.random.randn(self.config.fft_size) + 1j * np.random.randn(self.config.fft_size)
        iq_data += 1e-10
        _, power_spectrum, noise_floor = self.analyzer.analyze(iq_data)
        assert np.all(np.isfinite(power_spectrum))
        assert np.isfinite(noise_floor)

    def test_fft_size_variations(self):
        for fft_size in [512, 1024, 2048, 4096]:
            config = Config(fft_size=fft_size, sample_rate=2_000_000, center_frequency=100_000_000)
            analyzer = SpectrumAnalyzer(config)
            iq_data = np.random.randn(fft_size) + 1j * np.random.randn(fft_size)
            frequencies, power_spectrum, noise_floor = analyzer.analyze(iq_data)
            assert len(frequencies) == fft_size
            assert len(power_spectrum) == fft_size
            assert np.isfinite(noise_floor)

    def test_sample_rate_variations(self):
        for sample_rate in [1_000_000, 2_000_000, 4_000_000]:
            config = Config(fft_size=2048, sample_rate=sample_rate, center_frequency=100_000_000)
            analyzer = SpectrumAnalyzer(config)
            iq_data = np.random.randn(2048) + 1j * np.random.randn(2048)
            frequencies, _, _ = analyzer.analyze(iq_data)
            freq_res = analyzer.get_frequency_resolution()
            assert abs(freq_res - sample_rate / 2048) < 1e-6
            assert np.all(np.diff(frequencies) > 0)
