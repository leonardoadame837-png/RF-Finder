"""Centralized configuration for RF Finder."""

from dataclasses import dataclass


@dataclass
class Config:
    """RF Finder configuration parameters."""

    # Capture source settings
    source: str = "simulator"  # "simulator" or "sdr"
    sdr_device_index: int = 0
    sdr_gain: str | float = "auto"
    sample_rate: int = 2_000_000
    center_frequency: int = 100_000_000

    # DSP pipeline settings
    fft_size: int = 2048
    detection_threshold_db: float = 6.0
    minimum_signal_bandwidth_hz: int = 10_000

    # Display and storage
    waterfall_history_frames: int = 256
    database_path: str = "data/database/rf_finder.db"

    # Simulator-specific settings
    noise_floor_db: float = -80.0
    num_frames: int = 5


# Default configuration instance
default_config = Config()
