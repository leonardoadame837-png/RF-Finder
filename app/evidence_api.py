"""Evidence and localization helpers used by the tactical server."""

from app.evidence_report import build_report
from app.localization import build_heatmap, summarize_tracks


def investigation_report(investigation_store, observation_store, investigation_id: int) -> dict | None:
    investigation = investigation_store.get(investigation_id)
    if not investigation:
        return None
    observations = investigation_store.observations(investigation_id, observation_store)
    return build_report(observations, investigation)


def localization_payload(observation_store) -> dict:
    observations = observation_store.recent(5000)
    return {"heatmap": build_heatmap(observations), "tracks": summarize_tracks(observations)}
