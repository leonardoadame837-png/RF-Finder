"""Centralized configuration for RF Finder."""

from dataclasses import dataclass

from app.source_types import SourceType, normalize_source_type


@dataclass
class Config:
    """RF Finder configuration parameters."""

    # Capture source settings. ``source`` is retained for compatibility.
    source: str = "simulator"
    source_type: SourceType | None = None
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
    simulation_seed: int = 12345

    def __post_init__(self) -> None:
        if self.fft_size <= 0 or self.sample_rate <= 0:
            raise ValueError("fft_size and sample_rate must be positive")
        if self.center_frequency < 0:
            raise ValueError("center_frequency must be non-negative")
        if self.source_type is None:
            self.source_type = normalize_source_type(self.source)
        else:
            self.source_type = normalize_source_type(self.source_type)


default_config = Config()
