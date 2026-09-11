import sys
import types

import numpy as np
import pytest

from app.config import Config
from app.field_service import RFService
from app.sources.base import source_provenance
from app.sources.sdr import RTLSDRSource, SDRUnavailableError


def test_sdr_source_is_verified_hardware_provenance():
    source = RTLSDRSource(Config())
    provenance = source_provenance(source)
    assert provenance["source"] == "sdr"
    assert provenance["verified_rf"] is True
    assert provenance["simulated"] is False
    assert provenance["capture_kind"] == "hardware_iq"


def test_sdr_source_reports_missing_optional_driver(monkeypatch):
    real_import = __import__

    def blocked_import(name, *args, **kwargs):
        if name == "rtlsdr":
            raise ImportError("test: driver unavailable")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", blocked_import)
    with pytest.raises(SDRUnavailableError):
        RTLSDRSource(Config()).start()


def test_sdr_source_reads_expected_frame(monkeypatch):
    class FakeRtlSdr:
        def __init__(self, index):
            self.index = index
            self.sample_rate = None
            self.center_freq = None
            self.gain = None
            self.closed = False

        def read_samples(self, count):
            return np.ones(count, dtype=np.complex128)

        def close(self):
            self.closed = True

    fake_module = types.SimpleNamespace(RtlSdr=FakeRtlSdr)
    monkeypatch.setitem(sys.modules, "rtlsdr", fake_module)

    config = Config(fft_size=32, sample_rate=1_000_000, center_frequency=433_920_000)
    source = RTLSDRSource(config, device_index=1, gain=20.0)
    source.start()
    frame = source.generate_frame()

    assert frame.shape == (32,)
    assert np.iscomplexobj(frame)
    assert source.frame_index == 1
    assert source.status()["center_frequency_hz"] == 433_920_000
    source.stop()


def test_service_selects_sdr_from_config(monkeypatch):
    class FakeSource:
        frame_index = 0

        def start(self):
            pass

        def stop(self):
            pass

        def generate_frame(self):
            self.frame_index += 1
            return np.zeros(32, dtype=np.complex128)

        def status(self):
            return {"source": "sdr", "active": True}

    monkeypatch.setattr("app.sources.sdr.RTLSDRSource", lambda config, device_index, gain: FakeSource())
    service = RFService(Config(source="sdr", fft_size=32))
    assert service.source_name == "sdr"
    assert source_provenance(service.source)["verified_rf"] is True
