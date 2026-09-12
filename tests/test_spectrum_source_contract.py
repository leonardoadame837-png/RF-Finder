import numpy as np

from app.config import Config
from app.dsp.analyzer import SpectrumAnalyzer
from app.dsp.detector import SignalDetector
from app.sources.types import SourceType


def test_complex_iq_frequency_axis_spans_expected_band():
    cfg = Config(fft_size=2048, sample_rate=2_000_000, center_frequency=100_000_000)
    frequencies, _, _ = SpectrumAnalyzer(cfg).analyze(np.zeros(cfg.fft_size, dtype=complex))
    resolution = cfg.sample_rate / cfg.fft_size
    assert np.isclose(frequencies[0], cfg.center_frequency - cfg.sample_rate / 2)
    assert np.isclose(frequencies[-1], cfg.center_frequency + cfg.sample_rate / 2 - resolution)
    assert np.all(np.diff(frequencies) > 0)


def test_strong_complex_tone_is_source_labeled_and_serializable():
    cfg = Config(fft_size=2048, sample_rate=2_000_000, center_frequency=100_000_000,
                 minimum_signal_bandwidth_hz=500)
    analyzer = SpectrumAnalyzer(cfg)
    detector = SignalDetector(cfg)
    t = np.arange(cfg.fft_size) / cfg.sample_rate
    iq = 0.5 * np.exp(2j * np.pi * 250_000 * t)
    frequencies, power, noise = analyzer.analyze(iq)
    detections = detector.detect(frequencies, power, noise, source_type=SourceType.SIMULATED)
    assert detections
    payload = detections[0].to_dict()
    assert payload["source_type"] == "SIMULATED"
    assert payload["frequency_hz"] == payload["center_frequency_hz"]
    assert payload["power_dbfs"] == payload["peak_power_db"]
    assert payload["noise_floor_dbfs"] == payload["noise_floor_db"]
    assert np.isclose(payload["snr_db"], payload["power_dbfs"] - payload["noise_floor_dbfs"])
    assert 0.0 <= payload["confidence"] <= 0.99


def test_noise_only_input_has_no_detection_and_invalid_spectrum_is_safe():
    cfg = Config(fft_size=512, sample_rate=1_000_000, center_frequency=100_000_000,
                 minimum_signal_bandwidth_hz=500)
    analyzer = SpectrumAnalyzer(cfg)
    detector = SignalDetector(cfg)
    rng = np.random.default_rng(785)
    iq = (rng.standard_normal(cfg.fft_size) + 1j * rng.standard_normal(cfg.fft_size)) * 0.01
    f, p, n = analyzer.analyze(iq)
    assert detector.detect(f, p, n) == []
    bad = p.copy(); bad[0] = np.nan
    assert detector.detect(f, bad, n) == []
    assert detector.detect(np.array([]), np.array([]), n) == []


def test_imported_source_defaults_to_imported_measurement_not_simulated():
    from app.observation import RFObservation
    observation = RFObservation.now(frequency_hz=1e6, peak_power_db=-20, noise_floor_db=-60,
                                    snr_db=40, bandwidth_hz=1000,
                                    source_type=SourceType.IMPORTED_MEASUREMENT)
    data = observation.to_dict()
    assert data["source_type"] == "IMPORTED_MEASUREMENT"
    assert data["simulated"] is False
