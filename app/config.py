"""Centralized configuration for RF Finder."""

from dataclasses import dataclass


@dataclass
class Config:
    """RF Finder configuration parameters."""
    
    # Signal source settings
    source: str = "simulator"  # "simulator" or "sdr" (future)
    sample_rate: int = 2_000_000  # 2 MS/s (samples per second)
    center_frequency: int = 100_000_000  # 100 MHz (Hz)
    
    # DSP pipeline settings
    fft_size: int = 2048
    detection_threshold_db: float = 6.0  # dB above noise floor
    minimum_signal_bandwidth_hz: int = 10_000  # 10 kHz
    
    # Display and storage
    waterfall_history_frames: int = 256
    database_path: str = "data/database/rf_finder.db"
    
    # Simulator-specific settings
    noise_floor_db: float = -80.0
    num_frames: int = 5  # Number of frames to process
    

# Default configuration instance
default_config = Config()
