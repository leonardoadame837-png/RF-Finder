"""RF Signal Detector - Peak detection and characterization."""

import numpy as np
from dataclasses import dataclass
from typing import List


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
    """Detects RF signals above noise floor and characterizes them."""
    
    def __init__(self, config):
        """Initialize the signal detector.
        
        Args:
            config: Config object with detection_threshold_db, etc.
        """
        self.config = config
    
    def detect(self, frequencies: np.ndarray, power_spectrum: np.ndarray,
               noise_floor_db: float, frame_index: int = 0) -> List[Detection]:
        """Detect signals above noise floor threshold.
        
        Args:
            frequencies: Array of frequency values (Hz)
            power_spectrum: Power spectrum in dB
            noise_floor_db: Estimated noise floor in dB
            frame_index: Current frame number
            
        Returns:
            List of Detection objects for each detected signal
        """
        detections = []
        
        # Calculate detection threshold
        threshold = noise_floor_db + self.config.detection_threshold_db
        
        # Find peaks above threshold
        above_threshold = power_spectrum > threshold
        
        if not np.any(above_threshold):
            return detections
        
        # Find peak indices
        diff = np.diff(above_threshold.astype(int))
        starts = np.where(diff == 1)[0] + 1
        ends = np.where(diff == -1)[0] + 1
        
        # Handle edge cases
        if above_threshold[0]:
            starts = np.concatenate([[0], starts])
        if above_threshold[-1]:
            ends = np.concatenate([ends, [len(above_threshold)]])
        
        # Process each detected signal region
        for start, end in zip(starts, ends):
            region_power = power_spectrum[start:end]
            region_freq = frequencies[start:end]
            
            # Find peak within region
            peak_idx = np.argmax(region_power)
            peak_frequency = region_freq[peak_idx]
            peak_power = region_power[peak_idx]
            # Peak magnitude in linear scale from power: magnitude = sqrt(10^(dB/10))
            peak_magnitude = np.sqrt(10 ** (peak_power / 10))
            
            # Calculate SNR
            snr = peak_power - noise_floor_db
            
            # Estimate bandwidth (3dB bandwidth)
            peak_level_3db = peak_power - 3
            bandwidth_indices = np.where(region_power > peak_level_3db)[0]
            
            if len(bandwidth_indices) > 1:
                # Bandwidth is the frequency span between first and last point above 3dB
                bandwidth = region_freq[bandwidth_indices[-1]] - region_freq[bandwidth_indices[0]]
            else:
                bandwidth = self.config.sample_rate / self.config.fft_size
            
            # Ensure minimum bandwidth threshold
            if bandwidth >= self.config.minimum_signal_bandwidth_hz:
                detection = Detection(
                    center_frequency_hz=peak_frequency,
                    peak_power_db=peak_power,
                    noise_floor_db=noise_floor_db,
                    snr_db=snr,
                    bandwidth_hz=bandwidth,
                    peak_magnitude=peak_magnitude,
                    timestamp_frame=frame_index
                )
                detections.append(detection)
        
        # Sort by frequency
        detections.sort(key=lambda d: d.center_frequency_hz)
        
        return detections
