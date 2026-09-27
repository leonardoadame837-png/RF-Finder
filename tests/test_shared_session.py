import json
import threading
import urllib.request
from http.cookies import SimpleCookie

from app.api_auth import APIAuth
from app.auth import AuthManager
from app.config import Config
from app.field_service import RFService
from app.spectrum_server import create_server as create_spectrum_server
from app.tactical_server import create_server as create_tactical_server


class FakeSource:
    def __init__(self, frame_size=64):
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
        t = np.arange(self.frame_size)
        self.frame_index += 1
        return np.exp(2j * np.pi * 0.12 * t).astype(np.complex64)


def make_service(tmp_path):
    config = Config(
        source="simulator",
        sample_rate=2_000_000.0,
        center_frequency=100_000_000.0,
        fft_size=64,
        detection_threshold_db=6.0,
        minimum_signal_bandwidth_hz=10_000.0,
        waterfall_history_frames=4,
        database_path=str(tmp_path / "shared.db"),
        noise_floor_db=-80.0,
        num_frames=1,
    )
    return RFService(config, source=FakeSource(), scan_interval_s=0.01)


def request(base, path, method="GET", payload=None, cookie=None):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=2) as response:
        return response.status, dict(response.headers), json.loads(response.read())


def test_login_cookie_is_shared_between_tactical_and_spectrum(tmp_path):
    auth = AuthManager(tmp_path / "users.json", session_ttl=60)
    auth.create_account("tester", "correct horse battery")
    api = APIAuth(auth)
    service = make_service(tmp_path)
    service.scan_once()

    tactical = create_tactical_server(service, "127.0.0.1", 0, auth=api)
    spectrum = create_spectrum_server(service, "127.0.0.1", 0, auth=api)
    threads = []
    for server in (tactical, spectrum):
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        threads.append(thread)

    try:
        tactical_base = f"http://127.0.0.1:{tactical.server_port}"
        spectrum_base = f"http://127.0.0.1:{spectrum.server_port}"

        status, headers, login = request(
            tactical_base,
            "/api/auth/login",
            method="POST",
            payload={"username": "tester", "password": "correct horse battery"},
        )
        assert status == 200
        assert login["username"] == "tester"

        cookie = SimpleCookie()
        cookie.load(headers["Set-Cookie"])
        session_cookie = cookie["rf_finder_session"].OutputString()

        status, _, spectrum_payload = request(
            spectrum_base,
            "/api/spectrum",
            cookie=session_cookie,
        )
        assert status == 200
        assert len(spectrum_payload["frequencies_hz"]) == 64
    finally:
        for server in (tactical, spectrum):
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join(timeout=2)
