"""RF signal detection and characterization."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import List

import numpy as np

from app.sources.types import SourceType, normalize_source_type


@dataclass
class Detection:
    """A spectral candidate with explicit provenance and algorithmic confidence."""

    center_frequency_hz: float
    peak_power_db: float
    noise_floor_db: float
    snr_db: float
    bandwidth_hz: float
    peak_magnitude: float
    timestamp_frame: int = 0
    source_type: str = SourceType.UNKNOWN.value
    timestamp: str = ""
    confidence: float = 0.0

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
        data = asdict(self)
        data.update({
            "frequency_hz": float(self.center_frequency_hz),
            "power_dbfs": float(self.peak_power_db),
            "noise_floor_dbfs": float(self.noise_floor_db),
            "bandwidth_hz": float(self.bandwidth_hz),
            "snr_db": float(self.snr_db),
            "confidence": float(self.confidence),
            "source_type": normalize_source_type(self.source_type).value,
            "timestamp": self.timestamp or datetime.now(timezone.utc).isoformat(),
        })
        return data


class SignalDetector:
    """Detect signals above a robust noise baseline and characterize them."""

    def __init__(self, config):
        self.config = config

    @staticmethod
    def _confidence(snr_db: float, threshold_margin_db: float) -> float:
        """Algorithmic confidence; never proof of transmitter identity."""
        margin = max(0.0, snr_db - threshold_margin_db)
        return float(min(0.99, max(0.0, margin / 30.0 + 0.50)))

    def detect(self, frequencies: np.ndarray, power_spectrum: np.ndarray,
               noise_floor_db: float, frame_index: int = 0,
               source_type: SourceType | str = SourceType.UNKNOWN,
               timestamp: str | None = None) -> List[Detection]:
        """Detect contiguous signal regions above an adaptive threshold."""
        frequencies = np.asarray(frequencies)
        power_spectrum = np.asarray(power_spectrum)
        if frequencies.shape != power_spectrum.shape:
            raise ValueError("frequencies and power_spectrum must have the same shape")
        if frequencies.size == 0:
            return []
        if not np.all(np.isfinite(frequencies)) or not np.all(np.isfinite(power_spectrum)):
            return []
        if not np.isfinite(noise_floor_db):
            return []

        normalized_source = normalize_source_type(source_type)
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
            snr_db = peak_power - float(noise_floor_db)
            detections.append(Detection(
                center_frequency_hz=peak_frequency,
                peak_power_db=peak_power,
                noise_floor_db=float(noise_floor_db),
                snr_db=snr_db,
                bandwidth_hz=bandwidth,
                peak_magnitude=float(np.sqrt(10.0 ** (peak_power / 10.0))),
                timestamp_frame=frame_index,
                source_type=normalized_source.value,
                timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
                confidence=self._confidence(snr_db, threshold_margin_db),
            ))
        detections.sort(key=lambda detection: detection.center_frequency_hz)
        return detections
