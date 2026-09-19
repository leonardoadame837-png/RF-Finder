from app.vision import CameraRegistry, EventCorrelator, secret_env_name

def test_camera_registry_never_returns_password(tmp_path, monkeypatch):
    registry = CameraRegistry(str(tmp_path / "vision.db"))
    camera = registry.create(name="Test Camera", host="192.168.1.50", username="operator", audio_enabled=True)
    assert "password" not in camera
    assert "rtsp://" not in str(camera)
    assert camera["connection"] == "CREDENTIAL_REQUIRED"
    monkeypatch.setenv(secret_env_name(camera["id"]), "not-stored-in-db")
    loaded = registry.get(camera["id"])
    assert loaded["credential_configured"] is True

def test_camera_host_and_protocol_are_validated(tmp_path):
    registry = CameraRegistry(str(tmp_path / "vision.db"))
    try:
        registry.create(name="bad", host="http://example.com", protocol="http")
        assert False, "expected validation error"
    except ValueError:
        pass

def test_timestamp_correlation_does_not_create_rf_events():
    events = [
        {"event_id":"rf-1","event_type":"RF_DETECTION","source_id":"rf-source","source_type":"LIVE_MEASUREMENT","timestamp":"2026-09-19T03:00:00+00:00","payload":{"frequency_hz":433268285}},
        {"event_id":"audio-1","event_type":"AUDIO_EVENT","source_id":"camera-1","source_type":"CAMERA_AUDIO","timestamp":"2026-09-19T03:00:00.400000+00:00","payload":{"level_dbfs":-24}},
    ]
    groups = EventCorrelator(1000).correlate(events)
    assert len(groups) == 1
    assert {e["event_type"] for e in groups[0]["events"]} == {"RF_DETECTION","AUDIO_EVENT"}
    assert groups[0]["interpretation"].startswith("Temporal correlation only")

def test_events_outside_window_are_not_correlated():
    events = [
        {"event_id":"rf","event_type":"RF_DETECTION","timestamp":"2026-09-19T03:00:00+00:00"},
        {"event_id":"video","event_type":"VIDEO_SNAPSHOT","timestamp":"2026-09-19T03:00:02+00:00"},
    ]
    assert EventCorrelator(500).correlate(events) == []
