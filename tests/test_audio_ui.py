import threading
import urllib.error
import urllib.request
import wave
from io import BytesIO

import numpy as np

from app.api_auth import APIAuth
from app.auth import AuthManager
from app.config import Config
from app.field_service import RFService
from app.spectrum_server import create_server


class AudioSource:
    def __init__(self, frame_size):
        self.frame_size = frame_size
        self.frame_index = 0

    def start(self):
        pass

    def stop(self):
        pass

    def status(self):
        return {"source": "simulator", "running": True, "frame_index": self.frame_index}

    def generate_frame(self):
        self.frame_index += 1
        t = np.arange(self.frame_size, dtype=np.float64)
        return np.exp(2j * np.pi * 0.08 * t).astype(np.complex128)


def test_audio_endpoint_requires_auth_and_returns_wav(tmp_path):
    config = Config(
        source="simulator",
        sample_rate=200_000,
        center_frequency=100_000_000,
        fft_size=2048,
        waterfall_history_frames=2,
        database_path=str(tmp_path / "audio.db"),
        noise_floor_db=-80.0,
        detection_threshold_db=6.0,
        minimum_signal_bandwidth_hz=1000.0,
    )
    service = RFService(config, source=AudioSource(config.fft_size), scan_interval_s=0.1)
    service.scan_once()

    auth = AuthManager(tmp_path / "users.json", session_ttl=60)
    auth.create_account("tester", "correct horse battery")
    api = APIAuth(auth)
    session = api.login("tester", "correct horse battery")
    server = create_server(service, "127.0.0.1", 0, auth=api)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"

    try:
        try:
            urllib.request.urlopen(base + "/api/audio?mode=fm", timeout=2)
            assert False, "expected authentication failure"
        except urllib.error.HTTPError as exc:
            assert exc.code == 401

        request = urllib.request.Request(
            base + "/api/audio?mode=fm&bandwidth_hz=15000",
            headers={"Authorization": f"Bearer {session.token}"},
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            assert response.status == 200
            assert response.headers.get_content_type() == "audio/wav"
            payload = response.read()

        with wave.open(BytesIO(payload), "rb") as wav:
            assert wav.getnchannels() == 1
            assert wav.getsampwidth() == 2
            assert wav.getframerate() == 48_000
            assert wav.getnframes() > 100
    finally:
        api.logout(f"Bearer {session.token}")
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_rf_studio_ui_contains_audio_controls(tmp_path):
    config = Config(database_path=str(tmp_path / "ui.db"), fft_size=128)
    service = RFService(config, source=AudioSource(128))
    server = create_server(service, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}/spectrum", timeout=2) as response:
            html = response.read().decode()
        assert "Audio Start" in html
        assert "Audio Stop" in html
        assert "/api/audio?mode=" in html
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
