"""Data models for RF observations and conservative tactical classification."""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional


@dataclass
class RFObservation:
    """A timestamped RF measurement suitable for storage and map display."""

    timestamp: str
    frequency_hz: float
    peak_power_db: float
    noise_floor_db: float
    snr_db: float
    bandwidth_hz: float
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude_m: Optional[float] = None
    bearing_deg: Optional[float] = None
    source: str = "unknown"
    signal_class: str = "unknown"
    confidence: float = 0.0
    evidence: str = ""
    simulated: bool = False

    @classmethod
    def now(cls, **kwargs) -> "RFObservation":
        return cls(timestamp=datetime.now(timezone.utc).isoformat(), **kwargs)

    def to_dict(self) -> dict:
        return asdict(self)


def classify_observation(observation: RFObservation) -> RFObservation:
    """Apply conservative labels; RF characteristics alone do not prove intent or legality.

    A drone label is only assigned when an upstream receiver explicitly supplies
    Remote ID evidence. Ordinary 2.4/5.8 GHz energy is therefore not called a drone.
    """
    evidence = observation.evidence.lower()
    if "remote_id" in evidence or "remote id" in evidence:
        observation.signal_class = "possible_drone_remote_id"
        observation.confidence = max(observation.confidence, 0.85)
    elif observation.snr_db >= 20.0:
        observation.signal_class = "strong_rf_signal"
        observation.confidence = max(observation.confidence, 0.60)
    else:
        observation.signal_class = "rf_signal"
        observation.confidence = max(observation.confidence, 0.40)
    return observation
