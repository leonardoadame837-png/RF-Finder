"""Build neutral, provenance-preserving RF evidence reports."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable


PRIORITY_LABELS = (
    "normal_observation",
    "unusual_rf_activity",
    "persistent_interference_candidate",
    "high_priority_investigation_candidate",
)


def review_priority(observation: dict) -> str:
    """Return an operational review label, never a legal determination."""
    if observation.get("simulated"):
        return "normal_observation"
    snr = float(observation.get("snr_db", 0.0))
    if snr >= 35.0:
        return "high_priority_investigation_candidate"
    if snr >= 25.0:
        return "persistent_interference_candidate"
    if snr >= 20.0:
        return "unusual_rf_activity"
    return "normal_observation"


def build_report(observations: Iterable[dict], investigation: dict | None = None) -> dict:
    """Create a portable evidence package from measured observations.

    The report deliberately describes observations and review priority rather than
    declaring that an RF source is illegal or identifying a transmitter owner.
    """
    items = []
    for observation in observations:
        item = dict(observation)
        item["review_priority"] = review_priority(item)
        item["measurement_status"] = (
            "simulation" if item.get("simulated") else
            "verified_sdr_capture" if str(item.get("source", "")).lower() == "sdr" else
            "unverified_capture_source"
        )
        items.append(item)

    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "report_type": "passive_rf_observation",
        "legal_status": "No legal determination made",
        "methodology": "Passive RF measurement with receiver GPS correlation",
        "investigation": investigation,
        "observation_count": len(items),
        "observations": items,
        "limitations": [
            "Receiver coordinates identify the measurement position, not necessarily the transmitter position.",
            "RF characteristics alone do not establish that a transmission is illegal.",
            "Simulation data is not evidence of a real RF transmission.",
            "AI interpretation is advisory and does not replace measurement validation or authority review.",
        ],
        "recommended_next_step": "Human review and, when appropriate, referral to the relevant communications or public-safety authority.",
    }
