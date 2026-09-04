import json
import threading
import urllib.request

from app.config import Config
from app.field_service import RFService
from app.tactical_server import create_server


class FakeSource:
    def __init__(self, frame_size=128):
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
        return np.exp(2j * np.pi * 0.12 * t).astype(np.complex64)


def make_service(tmp_path):
    config = Config(
        source="simulator",
        sample_rate=2_000_000.0,
        center_frequency=100_000_000.0,
        fft_size=128,
        detection_threshold_db=6.0,
        minimum_signal_bandwidth_hz=10_000.0,
        waterfall_history_frames=4,
        database_path=str(tmp_path / "api.db"),
        noise_floor_db=-80.0,
        num_frames=1,
    )
    return RFService(config, source=FakeSource(), scan_interval_s=0.01)


def request_json(base_url, path, method="GET", payload=None):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(base_url + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=2) as response:
        return response.status, response.headers.get_content_type(), json.loads(response.read())


def test_live_spectrum_and_waterfall_endpoints(tmp_path):
    service = make_service(tmp_path)
    service.scan_once()
    server = create_server(service, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"

    try:
        status, content_type, spectrum = request_json(base, "/api/spectrum")
        assert status == 200
        assert content_type == "application/json"
        assert len(spectrum["frequencies_hz"]) == 128
        assert len(spectrum["power_db"]) == 128

        status, content_type, waterfall = request_json(base, "/api/waterfall")
        assert status == 200
        assert content_type == "application/json"
        assert waterfall["frame_count"] == 1
        assert waterfall["fft_size"] == 128
        assert len(waterfall["frames"]) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_status_observations_and_investigation_endpoints(tmp_path):
    service = make_service(tmp_path)
    service.scan_once()
    server = create_server(service, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"

    try:
        status, _, payload = request_json(base, "/api/status")
        assert status == 200
        assert payload["source"] == "fake"
        assert payload["frame_index"] == 1

        status, _, observations = request_json(base, "/api/observations?limit=10")
        assert status == 200
        assert isinstance(observations, list)

        status, _, investigations = request_json(base, "/api/investigations")
        assert status == 200
        assert investigations == []

        status, _, created = request_json(
            base,
            "/api/investigations",
            method="POST",
            payload={"title": "API case", "notes": "field test"},
        )
        assert status == 201
        assert created["title"] == "API case"
        assert created["notes"] == "field test"

        status, _, investigations = request_json(base, "/api/investigations")
        assert status == 200
        assert len(investigations) == 1
        assert investigations[0]["title"] == "API case"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_missing_api_route_returns_404(tmp_path):
    service = make_service(tmp_path)
    server = create_server(service, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"

    try:
        try:
            urllib.request.urlopen(base + "/api/does-not-exist", timeout=2)
            assert False, "expected HTTP 404"
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
