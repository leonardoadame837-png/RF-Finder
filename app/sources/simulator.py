"""RF Signal Simulator - Generates synthetic IQ data for testing."""

import numpy as np
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class SimulatedSignal:
    """Definition of a simulated RF signal."""
    frequency_offset_hz: int  # Offset from center frequency (Hz)
    power_dbm: float  # Signal power in dBm
    bandwidth_hz: int = 48_800  # Default bandwidth


class SignalSimulator:
    """Generates synthetic RF signals with realistic IQ data."""
    
    def __init__(self, config):
        """Initialize the signal simulator.
        
        Args:
            config: Config object with sample_rate, center_frequency, etc.
        """
        self.config = config
        self.signals: List[SimulatedSignal] = []
        self.frame_index = 0
        
    def add_signal(self, frequency_offset_hz: int, power_dbm: float, 
                   bandwidth_hz: int = 48_800) -> None:
        """Add a simulated signal.
        
        Args:
            frequency_offset_hz: Frequency offset from center (positive or negative)
            power_dbm: Signal power level in dBm
            bandwidth_hz: Signal bandwidth in Hz
        """
        self.signals.append(
            SimulatedSignal(
                frequency_offset_hz=frequency_offset_hz,
                power_dbm=power_dbm,
                bandwidth_hz=bandwidth_hz
            )
        )
    
    def start(self) -> None:
        """Start the simulator."""
        self.frame_index = 0
        if not self.signals:
            # Default test signals matching README example
            self.add_signal(frequency_offset_hz=10_000_000, power_dbm=-20.0)  # 10 MHz above
            self.add_signal(frequency_offset_hz=-25_000_000, power_dbm=-25.0)  # 25 MHz below
            self.add_signal(frequency_offset_hz=5_000_000, power_dbm=-30.0)  # 5 MHz above
    
    def stop(self) -> None:
        """Stop the simulator."""
        self.frame_index = 0
    
    def generate_frame(self) -> np.ndarray:
        """Generate one frame of complex IQ samples.
        
        Returns:
            Complex numpy array of shape (fft_size,) with IQ data
        """
        # Create noise (AWGN)
        noise_power = self._dbm_to_linear(self.config.noise_floor_db)
        noise_i = np.random.normal(0, np.sqrt(noise_power / 2), self.config.fft_size)
        noise_q = np.random.normal(0, np.sqrt(noise_power / 2), self.config.fft_size)
        iq_data = noise_i + 1j * noise_q
        
        # Add signals
        time_samples = np.arange(self.config.fft_size) / self.config.sample_rate
        for signal in self.signals:
            signal_freq = self.config.center_frequency + signal.frequency_offset_hz
            signal_power = self._dbm_to_linear(signal.power_dbm)
            signal_amplitude = np.sqrt(signal_power)
            
            # Complex exponential (IQ modulation)
            phase = 2 * np.pi * signal_freq * time_samples
            iq_data += signal_amplitude * np.exp(1j * phase)
        
        self.frame_index += 1
        return iq_data
    
    @staticmethod
    def _dbm_to_linear(power_dbm: float) -> float:
        """Convert power from dBm to linear (watts).
        
        Args:
            power_dbm: Power in dBm
            
        Returns:
            Power in linear scale (watts)
        """
        return 10 ** ((power_dbm - 30) / 10)
    
    def get_signal_info(self) -> str:
        """Return human-readable signal information."""
        lines = ["Simulated signals:"]
        for sig in self.signals:
            freq_mhz = (self.config.center_frequency + sig.frequency_offset_hz) / 1e6
            direction = "above" if sig.frequency_offset_hz > 0 else "below"
            offset_mhz = abs(sig.frequency_offset_hz) / 1e6
            lines.append(f"  • {offset_mhz:.0f} MHz {direction} center @ {sig.power_dbm} dBm")
        return "\n".join(lines)
