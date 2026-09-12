"""Data models for conservative RF observations."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional

from app.sources.types import SourceType, normalize_source_type


@dataclass
class RFObservation:
    """A timestamped RF observation with explicit provenance."""

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
    source_type: str = SourceType.UNKNOWN.value
    signal_class: str = "unknown"
    confidence: float = 0.0
    evidence: str = ""
    simulated: bool = False

    @classmethod
    def now(cls, **kwargs) -> "RFObservation":
        return cls(timestamp=datetime.now(timezone.utc).isoformat(), **kwargs)

    def __post_init__(self) -> None:
        normalized = normalize_source_type(self.source_type if self.source_type != SourceType.UNKNOWN.value else self.source)
        self.source_type = normalized.value
        self.simulated = normalized is SourceType.SIMULATED
        if self.source == "unknown":
            self.source = normalized.value.lower()

    def to_dict(self) -> dict:
        return asdict(self)


def classify_observation(observation: RFObservation) -> RFObservation:
    """Apply conservative labels; RF characteristics do not prove intent or legality."""
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
