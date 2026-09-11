from app.device_telemetry import TelemetryStore
from app.sources.base import source_provenance
from app.sources.simulator import SignalSimulator

from app.config import Config


def test_simulator_provenance_is_not_verified():
    source = SignalSimulator(Config())
    provenance = source_provenance(source)
    assert provenance["simulated"] is True
    assert provenance["verified_rf"] is False
    assert provenance["capture_kind"] == "synthetic_iq"


def test_device_telemetry_keeps_sensor_data_separate_from_rf():
    store = TelemetryStore()
    result = store.update(
        {
            "platform": "android",
            "client": "rf-finder-mobile",
            "latitude": 32.7157,
            "longitude": -117.1611,
            "heading_deg": 184.0,
            "acceleration_x": 0.1,
        }
    )
    assert result["platform"] == "android"
    assert result["latitude"] == 32.7157
    assert result["heading_deg"] == 184.0
    assert "power_db" not in result
    assert "frequency_hz" not in result
