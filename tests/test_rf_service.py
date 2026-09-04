import time

from app.config import Config
from app.field_service import RFService


class FakeSource:
    def __init__(self, frame_size=256):
        self.frame_size = frame_size
        self.running = False
        self.frame_index = 0

    def start(self):
        self.running = True

    def stop(self):
        self.running = False

    def status(self):
        return {"source": "fake", "running": self.running, "frame_index": self.frame_index}

    def generate_frame(self):
        import numpy as np

        self.frame_index += 1
        t = np.arange(self.frame_size)
        return np.exp(2j * np.pi * 0.08 * t).astype(np.complex64)


def make_config(tmp_path, fft_size=256, history=4):
    return Config(
        source="simulator",
        sample_rate=2_000_000,
        center_frequency=100_000_000,
        fft_size=fft_size,
        detection_threshold_db=6.0,
        minimum_signal_bandwidth_hz=10_000,
        waterfall_history_frames=history,
        database_path=str(tmp_path / "rf.db"),
        noise_floor_db=-80.0,
        num_frames=1,
    )


def test_scan_once_updates_spectrum_and_waterfall(tmp_path):
    source = FakeSource()
    service = RFService(make_config(tmp_path), source=source)

    result = service.scan_once()

    assert result is not None
    spectrum = service.latest_spectrum()
    assert spectrum["timestamp"]
    assert len(spectrum["frequencies_hz"]) == 256
    assert len(spectrum["power_db"]) == 256
    assert spectrum["sample_rate_hz"] == 2_000_000
    assert spectrum["center_frequency_hz"] == 100_000_000

    waterfall = service.waterfall()
    assert waterfall["frame_count"] == 1
    assert len(waterfall["frames"]) == 1
    assert len(waterfall["frames"][0]) == 256


def test_waterfall_is_bounded(tmp_path):
    source = FakeSource()
    service = RFService(make_config(tmp_path, history=3), source=source)

    for _ in range(7):
        service.scan_once()

    waterfall = service.waterfall()
    assert waterfall["frame_count"] == 3
    assert len(waterfall["frames"]) == 3


def test_service_start_stop_runs_background_scans(tmp_path):
    source = FakeSource()
    service = RFService(make_config(tmp_path), source=source, scan_interval_s=0.01)

    service.start()
    deadline = time.time() + 1.0
    while source.frame_index == 0 and time.time() < deadline:
        time.sleep(0.01)

    status = service.status()
    assert status["running"] is True
    assert status["frame_index"] > 0
    assert status["source"] == "fake"

    service.stop()
    assert service.status()["running"] is False
    assert source.running is False


def test_status_includes_gps_configuration(tmp_path, monkeypatch):
    monkeypatch.setenv("RF_FINDER_LAT", "32.7157")
    monkeypatch.setenv("RF_FINDER_LON", "-117.1611")
    monkeypatch.setenv("RF_FINDER_ALT_M", "20")

    service = RFService(make_config(tmp_path), source=FakeSource())
    status = service.status()

    assert status["gps"] == {
        "latitude": 32.7157,
        "longitude": -117.1611,
        "altitude_m": 20.0,
    }
