"""Typed contracts for source-aware spectrum API payloads."""

from typing import Literal, TypedDict

SourceTypeLiteral = Literal["SIMULATED", "IMPORTED_MEASUREMENT", "LIVE_MEASUREMENT", "UNKNOWN"]


class DetectionPayload(TypedDict):
    frequency_hz: float
    power_dbfs: float
    bandwidth_hz: float
    noise_floor_dbfs: float
    snr_db: float
    confidence: float
    source_type: SourceTypeLiteral
    timestamp: str


class SpectrumPayload(TypedDict):
    timestamp: str | None
    frequencies_hz: list[float]
    power_db: list[float]
    noise_floor_db: float | None
    center_frequency_hz: float
    sample_rate_hz: float
    source_type: SourceTypeLiteral
    detections: list[DetectionPayload]
