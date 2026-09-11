from app.evidence_report import build_report
from app.localization import build_heatmap, summarize_tracks


def test_heatmap_excludes_simulation_and_preserves_receiver_position():
    observations = [
        {"id": 1, "frequency_hz": 100_000_000, "snr_db": 30, "latitude": 32.70, "longitude": -117.16, "simulated": False},
        {"id": 2, "frequency_hz": 100_010_000, "snr_db": 20, "latitude": 32.71, "longitude": -117.15, "simulated": False},
        {"id": 3, "frequency_hz": 100_000_000, "snr_db": 99, "latitude": 32.70, "longitude": -117.16, "simulated": True},
    ]
    result = build_heatmap(observations)
    assert result["measurement_count"] == 2
    assert len(result["cells"]) == 2
    assert all(c["latitude"] in (32.70, 32.71) for c in result["cells"])


def test_tracks_group_nearby_frequencies():
    observations = [
        {"id": 1, "frequency_hz": 100_000_000, "latitude": 32.70, "longitude": -117.16, "simulated": False},
        {"id": 2, "frequency_hz": 100_010_000, "latitude": 32.71, "longitude": -117.15, "simulated": False},
        {"id": 3, "frequency_hz": 101_000_000, "latitude": 32.72, "longitude": -117.14, "simulated": False},
    ]
    tracks = summarize_tracks(observations)
    assert len(tracks) == 2
    assert tracks[0]["measurement_count"] == 2


def test_evidence_report_preserves_provenance():
    report = build_report([{"id": 1, "frequency_hz": 100_000_000, "snr_db": 10, "source": "sdr", "simulated": False}])
    assert report["observation_count"] == 1
    assert report["observations"][0]["measurement_status"] == "verified_sdr_capture"
    assert report["legal_status"] == "No legal determination made"
