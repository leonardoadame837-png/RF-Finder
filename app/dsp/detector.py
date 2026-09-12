"""RF Signal Detector - Peak detection and characterization."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import List

import numpy as np

from app.source_types import SourceType, normalize_source_type


@dataclass
class Detection:
    """A measurable spectral peak; confidence is algorithmic, not device identity proof."""

    center_frequency_hz: float
    peak_power_db: float
    noise_floor_db: float
    snr_db: float
    bandwidth_hz: float
    peak_magnitude: float
    timestamp_frame: int = 0
    confidence: float = 0.0
    source_type: SourceType = SourceType.UNKNOWN
    timestamp: str = ""

    @property
    def frequency_hz(self) -> float:
        return self.center_frequency_hz

    @property
    def power_dbfs(self) -> float:
        return self.peak_power_db

    @property
    def noise_floor_dbfs(self) -> float:
        return self.noise_floor_db

    def to_dict(self) -> dict:
        """Serialize using the stable API contract."""
        return {
            "frequency_hz": float(self.frequency_hz),
            "power_dbfs": float(self.power_dbfs),
            "bandwidth_hz": float(self.bandwidth_hz),
            "noise_floor_dbfs": float(self.noise_floor_dbfs),
            "snr_db": float(self.snr_db),
            "confidence": float(self.confidence),
            "source_type": normalize_source_type(self.source_type).value,
            "timestamp": self.timestamp,
        }


class SignalDetector:
    """Detect contiguous signal regions above a robust noise baseline."""

    def __init__(self, config):
        self.config = config

    def detect(
        self,
        frequencies: np.ndarray,
        power_spectrum: np.ndarray,
        noise_floor_db: float,
        frame_index: int = 0,
        source_type: SourceType | str = SourceType.UNKNOWN,
        timestamp: str | None = None,
    ) -> List[Detection]:
        frequencies = np.asarray(frequencies, dtype=float).reshape(-1)
        power_spectrum = np.asarray(power_spectrum, dtype=float).reshape(-1)
        if frequencies.shape != power_spectrum.shape:
            raise ValueError("frequencies and power_spectrum must have the same shape")
        if frequencies.size == 0:
            return []
        finite = np.isfinite(frequencies) & np.isfinite(power_spectrum)
        if not np.all(finite) or not np.isfinite(noise_floor_db):
            return []

        source = normalize_source_type(source_type)
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        threshold_margin_db = max(float(self.config.detection_threshold_db), 15.0)
        threshold = float(noise_floor_db) + threshold_margin_db
        above_threshold = power_spectrum > threshold
        if not np.any(above_threshold):
            return []

        changes = np.diff(above_threshold.astype(np.int8))
        starts = np.where(changes == 1)[0] + 1
        ends = np.where(changes == -1)[0] + 1
        if above_threshold[0]:
            starts = np.concatenate(([0], starts))
        if above_threshold[-1]:
            ends = np.concatenate((ends, [len(above_threshold)]))

        detections: List[Detection] = []
        frequency_resolution = float(self.config.sample_rate) / float(self.config.fft_size)

        for start, end in zip(starts, ends):
            region_power = power_spectrum[start:end]
            region_freq = frequencies[start:end]
            peak_idx = int(np.argmax(region_power))
            peak_power = float(region_power[peak_idx])
            peak_frequency = float(region_freq[peak_idx])
            peak_level_3db = peak_power - 3.0
            bandwidth_indices = np.where(region_power >= peak_level_3db)[0]
            if len(bandwidth_indices) > 1:
                bandwidth = float(region_freq[bandwidth_indices[-1]] - region_freq[bandwidth_indices[0]])
            else:
                bandwidth = frequency_resolution
            if bandwidth < float(self.config.minimum_signal_bandwidth_hz):
                continue

            snr = peak_power - float(noise_floor_db)
            # Algorithmic confidence increases with SNR above the detection
            # threshold and is capped below 1.0. It is never an identity claim.
            confidence = min(0.99, max(0.0, 0.5 + 0.02 * (snr - threshold_margin_db)))
            detections.append(
                Detection(
                    center_frequency_hz=peak_frequency,
                    peak_power_db=peak_power,
                    noise_floor_db=float(noise_floor_db),
                    snr_db=snr,
                    bandwidth_hz=max(bandwidth, frequency_resolution),
                    peak_magnitude=float(10.0 ** (peak_power / 20.0)),
                    timestamp_frame=frame_index,
                    confidence=confidence,
                    source_type=source,
                    timestamp=ts,
                )
            )

        detections.sort(key=lambda detection: detection.center_frequency_hz)
        return detections
