import numpy as np

from app.config import Config
from app.dsp.analyzer import SpectrumAnalyzer
from app.dsp.detector import SignalDetector
from app.source_types import SourceType


def cfg():
    return Config(fft_size=1024, sample_rate=1_000_000, center_frequency=100_000_000, minimum_signal_bandwidth_hz=500, detection_threshold_db=6.0)


def test_complex_iq_frequency_axis_spans_centered_sample_rate():
    c=cfg(); a=SpectrumAnalyzer(c); iq=np.zeros(c.fft_size,dtype=complex)
    f,_,_=a.analyze(iq)
    assert np.isclose(f[0],c.center_frequency-c.sample_rate/2)
    assert np.isclose(f[-1],c.center_frequency+c.sample_rate/2-c.sample_rate/c.fft_size)
    assert np.all(np.diff(f)>0)


def test_single_tone_detection_carries_source_and_confidence():
    c=cfg(); a=SpectrumAnalyzer(c); d=SignalDetector(c); t=np.arange(c.fft_size)/c.sample_rate
    iq=.5*np.exp(2j*np.pi*100_000*t)+.001*(np.ones(c.fft_size)+1j*np.ones(c.fft_size))
    f,p,n=a.analyze(iq); ds=d.detect(f,p,n,source_type=SourceType.SIMULATED,timestamp="2026-01-01T00:00:00Z")
    assert ds
    peak=min(ds,key=lambda x:abs(x.frequency_hz-100_100_000))
    assert abs(peak.frequency_hz-100_100_000)<a.get_frequency_resolution()
    assert peak.snr_db>15
    assert 0<=peak.confidence<=.99
    assert peak.to_dict()["source_type"]=="SIMULATED"


def test_noise_only_has_no_detection():
    c=cfg(); a=SpectrumAnalyzer(c); d=SignalDetector(c); rng=np.random.default_rng(7)
    iq=.01*(rng.standard_normal(c.fft_size)+1j*rng.standard_normal(c.fft_size))
    f,p,n=a.analyze(iq)
    assert d.detect(f,p,n)==[]


def test_multiple_peaks_are_returned_sorted():
    c=cfg(); a=SpectrumAnalyzer(c); d=SignalDetector(c); t=np.arange(c.fft_size)/c.sample_rate
    iq=.4*np.exp(2j*np.pi*(-200_000)*t)+.3*np.exp(2j*np.pi*200_000*t)
    f,p,n=a.analyze(iq); ds=d.detect(f,p,n,source_type=SourceType.IMPORTED_MEASUREMENT)
    assert len(ds)>=2
    assert [x.frequency_hz for x in ds]==sorted(x.frequency_hz for x in ds)
    assert all(x.source_type is SourceType.IMPORTED_MEASUREMENT for x in ds)


def test_empty_and_invalid_input_are_safe():
    c=cfg(); a=SpectrumAnalyzer(c)
    try:a.analyze(np.array([],dtype=complex))
    except ValueError:pass
    else:raise AssertionError("empty input must be rejected")
    bad=np.zeros(c.fft_size,dtype=complex); bad[0]=np.nan+1j
    try:a.analyze(bad)
    except ValueError:pass
    else:raise AssertionError("invalid input must be rejected")


def test_detection_serialization_matches_api_contract():
    c=cfg(); a=SpectrumAnalyzer(c); d=SignalDetector(c); t=np.arange(c.fft_size)/c.sample_rate; iq=.5*np.exp(2j*np.pi*50_000*t)
    f,p,n=a.analyze(iq); item=d.detect(f,p,n,source_type=SourceType.IMPORTED_MEASUREMENT)[0].to_dict()
    assert set(item)=={"frequency_hz","power_dbfs","bandwidth_hz","noise_floor_dbfs","snr_db","confidence","source_type","timestamp"}
