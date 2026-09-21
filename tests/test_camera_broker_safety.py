import pytest

from app.camera_broker import CameraBroker


def test_rtsp_override_rejects_non_rtsp_scheme(monkeypatch):
    monkeypatch.setenv("RF_FINDER_CAMERA_1_RTSP_URL", "http://127.0.0.1/stream")
    with pytest.raises(ValueError, match="rtsp:// or rtsps://"):
        CameraBroker._rtsp_url({"id": 1, "protocol": "rtsp", "host": "127.0.0.1", "port": 554})


def test_rtsp_override_requires_hostname(monkeypatch):
    monkeypatch.setenv("RF_FINDER_CAMERA_1_RTSP_URL", "rtsp:///missing-host")
    with pytest.raises(ValueError, match="rtsp:// or rtsps://"):
        CameraBroker._rtsp_url({"id": 1, "protocol": "rtsp", "host": "127.0.0.1", "port": 554})


def test_rtsp_url_brackets_ipv6_host():
    url = CameraBroker._rtsp_url({
        "id": 2, "protocol": "rtsps", "host": "2001:db8::10", "port": 8554,
        "username": "", "stream_path": "/live",
    })
    assert url == "rtsps://[2001:db8::10]:8554/live"
