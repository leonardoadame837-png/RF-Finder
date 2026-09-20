from app.camera_broker import CameraBroker
from app.vision import CameraRegistry, VisionEventStore, secret_env_name


def test_camera_stream_path_and_event_store(tmp_path, monkeypatch):
    registry = CameraRegistry(str(tmp_path / "vision.db"))
    camera = registry.create(
        name="Cam720", host="192.168.1.50", username="operator",
        stream_path="/live/ch00_0", audio_enabled=True,
    )
    assert camera["stream_path"] == "/live/ch00_0"
    store = VisionEventStore(str(tmp_path / "vision.db"))
    event = {
        "event_id": "cam-1", "event_type": "AUDIO_EVENT",
        "source_id": "camera-1", "source_type": "CAMERA_AUDIO",
        "timestamp": "2026-09-19T03:00:00+00:00",
        "payload": {"level_dbfs": -24},
    }
    assert store.add(event)["source_type"] == "CAMERA_AUDIO"
    assert store.recent(10)[0]["payload"]["level_dbfs"] == -24


def test_broker_builds_server_side_rtsp_url(tmp_path, monkeypatch):
    registry = CameraRegistry(str(tmp_path / "vision.db"))
    camera = registry.create(name="Cam720", host="192.168.1.50", username="operator", stream_path="/live")
    monkeypatch.setenv(secret_env_name(camera["id"]), "p@ss word")
    url = CameraBroker._rtsp_url(camera)
    assert url == f"rtsp://operator:p%40ss%20word@192.168.1.50:554/live"
