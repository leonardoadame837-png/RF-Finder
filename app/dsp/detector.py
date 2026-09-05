"""RF Signal Detector - Peak detection and characterization."""

from dataclasses import dataclass
from typing import List

import numpy as np


@dataclass
class Detection:
    """Record of a detected RF signal."""
    center_frequency_hz: float
    peak_power_db: float
    noise_floor_db: float
    snr_db: float
    bandwidth_hz: float
    peak_magnitude: float
    timestamp_frame: int = 0


class SignalDetector:
    """Detect signals above a robust noise baseline and characterize them."""

    def __init__(self, config):
        self.config = config

    def detect(
        self,
        frequencies: np.ndarray,
        power_spectrum: np.ndarray,
        noise_floor_db: float,
        frame_index: int = 0,
    ) -> List[Detection]:
        """Detect contiguous signal regions above an adaptive threshold.

        Broadband FFT noise produces random peaks that can sit more than the
        user-configured threshold above the median noise floor. A conservative
        15 dB minimum margin keeps those statistical excursions from becoming
        detections while preserving the configured threshold as the lower bound.
        """
        frequencies = np.asarray(frequencies)
        power_spectrum = np.asarray(power_spectrum)
        if frequencies.shape != power_spectrum.shape:
            raise ValueError("frequencies and power_spectrum must have the same shape")
        if frequencies.size == 0:
            return []
        if not np.all(np.isfinite(power_spectrum)):
            return []

        # The analyzer supplies a robust median noise floor. For an FFT of
        # broadband Gaussian noise, the largest bin is expected to exceed the
        # median by roughly 10-13 dB. Requiring 15 dB provides a practical
        # false-alarm guard for the detector without suppressing strong tones.
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

            # Estimate occupied 3 dB bandwidth within the detected region.
            peak_level_3db = peak_power - 3.0
            bandwidth_indices = np.where(region_power >= peak_level_3db)[0]
            if len(bandwidth_indices) > 1:
                bandwidth = float(
                    region_freq[bandwidth_indices[-1]] - region_freq[bandwidth_indices[0]]
                )
            else:
                bandwidth = frequency_resolution

            if bandwidth < float(self.config.minimum_signal_bandwidth_hz):
                continue

            detections.append(
                Detection(
                    center_frequency_hz=peak_frequency,
                    peak_power_db=peak_power,
                    noise_floor_db=float(noise_floor_db),
                    snr_db=peak_power - float(noise_floor_db),
                    bandwidth_hz=bandwidth,
                    peak_magnitude=float(np.sqrt(10.0 ** (peak_power / 10.0))),
                    timestamp_frame=frame_index,
                )
            )

        detections.sort(key=lambda detection: detection.center_frequency_hz)
        return detections
