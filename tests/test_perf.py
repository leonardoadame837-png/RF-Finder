"""Performance benchmarks for RF pipeline.

This module measures the throughput and latency of core DSP operations.
Run with: python -m pytest tests/test_perf.py -v --benchmark-only
"""

import pytest
import numpy as np
import time
from app.config import Config
from app.dsp.analyzer import SpectrumAnalyzer
from app.dsp.detector import SignalDetector


class TestAnalyzerPerformance:
    """Benchmark spectrum analyzer throughput and latency."""
    
    @pytest.fixture
    def config(self):
        """Standard test configuration."""
        return Config(fft_size=2048, sample_rate=2_000_000, center_frequency=100_000_000)
    
    @pytest.fixture
    def analyzer(self, config):
        """Instantiated spectrum analyzer."""
        return SpectrumAnalyzer(config)
    
    @pytest.fixture
    def test_signal(self, config):
        """Generate test IQ data (2048 complex samples)."""
        iq_data = np.random.randn(config.fft_size) + 1j * np.random.randn(config.fft_size)
        return iq_data
    
    def test_analyze_single_frame(self, benchmark, analyzer, test_signal):
        """Benchmark: Single FFT analysis pass.
        
        Target: < 2 ms per frame (2048 samples at 2 MS/s = 1 ms worth of data)
        """
        result = benchmark(analyzer.analyze, test_signal)
        frequencies, power_spectrum, noise_floor = result
        
        assert len(frequencies) == 2048
        assert len(power_spectrum) == 2048
        assert np.isfinite(noise_floor)
    
    def test_analyze_throughput_burst(self, benchmark, analyzer, config):
        """Benchmark: Process multiple frames in rapid succession.
        
        Real-world: 100 frames at 2 MS/s = 50ms of RF data
        """
        def process_frames():
            frames = [
                np.random.randn(config.fft_size) + 1j * np.random.randn(config.fft_size)
                for _ in range(100)
            ]
            for frame in frames:
                analyzer.analyze(frame)
        
        benchmark(process_frames)
    
    def test_frequency_array_stability(self, analyzer, config):
        """Verify: Frequency array does not change between calls.
        
        Used to detect if pre-computation is working.
        """
        iq_data = np.random.randn(config.fft_size) + 1j * np.random.randn(config.fft_size)
        
        freq1, _, _ = analyzer.analyze(iq_data)
        freq2, _, _ = analyzer.analyze(iq_data)
        
        # Should be identical (not just close)
        assert np.array_equal(freq1, freq2), "Frequency arrays should be identical"
    
    def test_noise_floor_calculation_time(self, benchmark, analyzer, test_signal):
        """Benchmark: Noise floor estimation (percentile operation).
        
        Currently slow; target for optimization.
        """
        analyzer.analyze(test_signal)  # Warm up
        
        # Time just the analyze call
        def analyze_wrapper():
            _, _, noise = analyzer.analyze(test_signal)
            return noise
        
        benchmark(analyze_wrapper)


class TestDetectorPerformance:
    """Benchmark signal detector throughput."""
    
    @pytest.fixture
    def config(self):
        """Standard test configuration."""
        return Config(fft_size=2048, sample_rate=2_000_000, center_frequency=100_000_000)
    
    @pytest.fixture
    def analyzer(self, config):
        """Instantiated spectrum analyzer."""
        return SpectrumAnalyzer(config)
    
    @pytest.fixture
    def detector(self, config):
        """Instantiated signal detector."""
        return SignalDetector(config)
    
    @pytest.fixture
    def spectrum_data(self, analyzer, config):
        """Generate realistic spectrum (signal + noise)."""
        iq_data = np.random.randn(config.fft_size) + 1j * np.random.randn(config.fft_size)
        frequencies, power_spectrum, noise_floor = analyzer.analyze(iq_data)
        return frequencies, power_spectrum, noise_floor
    
    def test_detect_single_frame(self, benchmark, detector, spectrum_data):
        """Benchmark: Peak detection on single spectrum.
        
        Target: < 1 ms (typically < 0.1 ms)
        """
        frequencies, power_spectrum, noise_floor = spectrum_data
        result = benchmark(detector.detect, frequencies, power_spectrum, noise_floor, 1)
        
        # Result is list of Detection objects
        assert isinstance(result, list)
    
    def test_detect_multiple_signals(self, benchmark, detector, config):
        """Benchmark: Detection with multiple signals present.
        
        Simulates realistic 5-10 signal scenario.
        """
        analyzer = SpectrumAnalyzer(config)
        
        def detect_noisy_spectrum():
            # Synthetic spectrum with multiple peaks
            iq_data = np.random.randn(config.fft_size) + 1j * np.random.randn(config.fft_size)
            # Inject artificial peaks for realism
            iq_data[100:110] += 5.0
            iq_data[500:515] += 3.0
            iq_data[1500:1520] += 4.0
            
            frequencies, power_spectrum, noise_floor = analyzer.analyze(iq_data)
            detections = detector.detect(frequencies, power_spectrum, noise_floor, 1)
            return detections
        
        benchmark(detect_noisy_spectrum)
    
    def test_detect_empty_spectrum(self, benchmark, detector, config):
        """Benchmark: Detection with no signals (worst case for threshold check).
        
        Should be fast (~microseconds).
        """
        analyzer = SpectrumAnalyzer(config)
        
        def detect_noise_only():
            iq_data = np.random.randn(config.fft_size) + 1j * np.random.randn(config.fft_size)
            frequencies, power_spectrum, noise_floor = analyzer.analyze(iq_data)
            # No signals, just noise
            return detector.detect(frequencies, power_spectrum, noise_floor + 50, 1)
        
        benchmark(detect_noise_only)


class TestEndToEndPipeline:
    """Benchmark complete RF processing pipeline."""
    
    @pytest.fixture
    def config(self):
        """Standard test configuration."""
        return Config(
            fft_size=2048,
            sample_rate=2_000_000,
            center_frequency=100_000_000,
            num_frames=10
        )
    
    @pytest.fixture
    def pipeline(self, config):
        """Complete DSP pipeline."""
        return {
            'analyzer': SpectrumAnalyzer(config),
            'detector': SignalDetector(config),
            'config': config
        }
    
    def test_pipeline_frame_latency(self, benchmark, pipeline):
        """Benchmark: Latency from raw IQ data to detections.
        
        Should be < 5 ms per frame for interactive use.
        """
        analyzer = pipeline['analyzer']
        detector = pipeline['detector']
        config = pipeline['config']
        
        def process_one_frame():
            iq_data = np.random.randn(config.fft_size) + 1j * np.random.randn(config.fft_size)
            frequencies, power_spectrum, noise_floor = analyzer.analyze(iq_data)
            detections = detector.detect(frequencies, power_spectrum, noise_floor, 1)
            return detections
        
        result = benchmark(process_one_frame)
        assert isinstance(result, list)
    
    def test_pipeline_throughput_10_frames(self, benchmark, pipeline):
        """Benchmark: Sustained throughput over 10 frames (~5 ms of RF data).
        
        Real-time requirement: 10 frames should complete in < 50 ms.
        """
        analyzer = pipeline['analyzer']
        detector = pipeline['detector']
        config = pipeline['config']
        
        def process_frames():
            for frame_num in range(config.num_frames):
                iq_data = np.random.randn(config.fft_size) + 1j * np.random.randn(config.fft_size)
                frequencies, power_spectrum, noise_floor = analyzer.analyze(iq_data)
                detector.detect(frequencies, power_spectrum, noise_floor, frame_num)
        
        benchmark(process_frames)


class TestRegressionGuards:
    """Tests to detect performance regressions.
    
    These are soft assertions that warn about slowdowns but don't fail CI.
    """
    
    @pytest.fixture
    def config(self):
        return Config(fft_size=2048, sample_rate=2_000_000)
    
    @pytest.fixture
    def analyzer(self, config):
        return SpectrumAnalyzer(config)
    
    def test_analyzer_under_5ms_per_frame(self, analyzer, config):
        """Guard: Analyzer must stay under 5 ms per frame.
        
        2048 FFT on modern CPU typically: 0.5-1 ms
        Percentile calculation: 1-2 ms
        Total: < 5 ms is safe margin
        """
        iq_data = np.random.randn(config.fft_size) + 1j * np.random.randn(config.fft_size)
        
        start = time.perf_counter()
        for _ in range(100):
            analyzer.analyze(iq_data)
        elapsed = time.perf_counter() - start
        
        avg_time_ms = (elapsed / 100) * 1000
        print(f"\nAnalyzer: {avg_time_ms:.2f} ms/frame (target: < 5 ms)")
        
        assert avg_time_ms < 5.0, f"Analyzer regression: {avg_time_ms:.2f} ms > 5 ms"
    
    def test_detector_under_1ms_per_frame(self, config):
        """Guard: Detector must stay under 1 ms per frame.
        
        Peak finding: typically < 0.1 ms
        """
        analyzer = SpectrumAnalyzer(config)
        detector = SignalDetector(config)
        iq_data = np.random.randn(config.fft_size) + 1j * np.random.randn(config.fft_size)
        
        frequencies, power_spectrum, noise_floor = analyzer.analyze(iq_data)
        
        start = time.perf_counter()
        for _ in range(100):
            detector.detect(frequencies, power_spectrum, noise_floor, 1)
        elapsed = time.perf_counter() - start
        
        avg_time_ms = (elapsed / 100) * 1000
        print(f"Detector: {avg_time_ms:.2f} ms/frame (target: < 1 ms)")
        
        assert avg_time_ms < 1.0, f"Detector regression: {avg_time_ms:.2f} ms > 1 ms"
