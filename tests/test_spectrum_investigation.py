from app.investigations import InvestigationStore
from app.observation import RFObservation
from app.sources.types import SourceType
from app.storage import ObservationStore


def test_detection_observation_can_be_attached_to_investigation(tmp_path):
    db = str(tmp_path / "rf.sqlite")
    observations = ObservationStore(db)
    investigations = InvestigationStore(db)
    obs_id = observations.add(RFObservation.now(
        frequency_hz=100_250_000,
        peak_power_db=-20.0,
        noise_floor_db=-70.0,
        snr_db=50.0,
        bandwidth_hz=1000.0,
        source_type=SourceType.IMPORTED_MEASUREMENT,
        confidence=0.9,
    ))
    investigation = investigations.create("Spectrum review", "Analyst-created observation")
    assert investigations.attach_observation(investigation["id"], obs_id)
    saved = investigations.get(investigation["id"])
    assert saved["observation_ids"] == [obs_id]
