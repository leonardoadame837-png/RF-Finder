import socket
import threading
import time

import numpy as np

from app.config import Config
from app.field_service import RFService
from app.sources.network import RTLTCPSource
from app.sources.simulator import SignalSimulator
from app.tactical_server import create_server


def test_simulator_dsp_detector_sqlite_pipeline(tmp_path):
    config = Config(
        source="simulator",
        fft_size=256,
        sample_rate=2_000_000,
        center_frequency=100_000_000,
        database_path=str(tmp_path / "pipeline.db"),
        waterfall_history_frames=4,
        num_frames=3,
    )
    service = RFService(config, source=SignalSimulator(config))

    results = [service.scan_once() for _ in range(3)]
    latest = service.latest_spectrum()

    assert [result["frame_index"] for result in results] == [1, 2, 3]
    assert latest["source_type"] == "simulated"
    assert len(latest["frequencies_hz"]) == 256
    assert len(latest["power_db"]) == 256
    assert latest["provenance"]["simulated"] is True
    assert latest["provenance"]["verified_rf"] is False
    assert service.waterfall()["frame_count"] == 3
    assert isinstance(service.observations(limit=20), list)


def test_tactical_ui_route_and_api_are_reachable(tmp_path):
    config = Config(fft_size=64, database_path=str(tmp_path / "ui.db"))
    service = RFService(config, source=SignalSimulator(config))
    service.scan_once()
    server = create_server(service, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        import urllib.request

        base = f"http://127.0.0.1:{server.server_port}"
        with urllib.request.urlopen(base + "/tactical", timeout=2) as response:
            html = response.read().decode("utf-8")
            assert response.status == 200
            assert "RF Finder" in html
        with urllib.request.urlopen(base + "/api/spectrum", timeout=2) as response:
            assert response.status == 200
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _rtl_tcp_test_server(frame_payload, command_count=15):
    ready = threading.Event()
    done = threading.Event()
    state = {"address": None, "commands": b"", "error": None}

    def run():
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(3)
        state["address"] = listener.getsockname()
        ready.set()
        try:
            conn, _ = listener.accept()
            conn.settimeout(3)
            with conn:
                conn.sendall(b"RTL0" + (1).to_bytes(4, "big") + (28).to_bytes(4, "big"))
                data = bytearray()
                while len(data) < command_count:
                    chunk = conn.recv(command_count - len(data))
                    if not chunk:
                        break
                    data.extend(chunk)
                state["commands"] = bytes(data)
                conn.sendall(frame_payload)
                time.sleep(0.1)
        except Exception as exc:
            state["error"] = exc
        finally:
            listener.close()
            done.set()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    assert ready.wait(2)
    return state, done, thread


def test_network_sdr_end_to_end_without_hardware():
    config = Config(
        source="network_sdr",
        fft_size=8,
        sample_rate=1_000_000,
        center_frequency=100_000_000,
    )
    payload = bytes([127, 127] * config.fft_size)
    state, done, thread = _rtl_tcp_test_server(payload)
    host, port = state["address"]
    source = RTLTCPSource(config, host=host, port=port, timeout_s=2)

    source.start()
    frame = source.generate_frame()

    assert frame.shape == (8,)
    assert np.allclose(frame, 0j, atol=1 / 127.5)
    assert source.status()["center_frequency_hz"] == 100_000_000.0
    assert source.status()["sample_rate_hz"] == 1_000_000.0
    assert state["error"] is None
    assert len(state["commands"]) == 15

    source.set_frequency(101_000_000)
    source.set_sample_rate(2_000_000)
    assert source.status()["center_frequency_hz"] == 101_000_000.0
    assert source.status()["sample_rate_hz"] == 2_000_000.0

    source.stop()
    assert done.wait(2)
    thread.join(timeout=2)


def test_network_metadata_reaches_dsp_and_waterfall():
    class DynamicSource:
        frame_index = 0

        def start(self):
            pass

        def stop(self):
            pass

        def generate_frame(self):
            self.frame_index += 1
            return np.ones(32, dtype=np.complex128)

        def status(self):
            return {
                "source": "network_sdr",
                "center_frequency_hz": 433_920_000.0,
                "sample_rate_hz": 1_024_000.0,
                "last_timestamp": "2026-09-16T12:00:00+00:00",
            }

    config = Config(fft_size=32, database_path=":memory:")
    service = RFService(config, source=DynamicSource())
    service.scan_once()

    latest = service.latest_spectrum()
    waterfall = service.waterfall()
    status = service.status()

    assert latest["center_frequency_hz"] == 433_920_000.0
    assert latest["sample_rate_hz"] == 1_024_000.0
    assert waterfall["center_frequency_hz"] == 433_920_000.0
    assert waterfall["sample_rate_hz"] == 1_024_000.0
    assert status["center_frequency_hz"] == 433_920_000.0
    assert status["sample_rate_hz"] == 1_024_000.0
