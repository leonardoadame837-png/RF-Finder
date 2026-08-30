"""RF Signal Simulator - Generates synthetic IQ data for testing."""

import numpy as np
from dataclasses import dataclass
from typing import List


@dataclass
class SimulatedSignal:
    """Definition of a simulated RF signal."""
    frequency_offset_hz: int
    power_dbm: float
    bandwidth_hz: int = 48_800


class SignalSimulator:
    """Generates synthetic RF signals with realistic IQ data."""

    def __init__(self, config):
        self.config = config
        self.signals: List[SimulatedSignal] = []
        self.frame_index = 0
        self.running = False

    def add_signal(self, frequency_offset_hz: int, power_dbm: float,
                   bandwidth_hz: int = 48_800) -> None:
        self.signals.append(SimulatedSignal(
            frequency_offset_hz=frequency_offset_hz,
            power_dbm=power_dbm,
            bandwidth_hz=bandwidth_hz,
        ))

    def start(self) -> None:
        """Start the simulator and load default test signals if needed."""
        self.frame_index = 0
        self.running = True
        if not self.signals:
            self.add_signal(10_000_000, -20.0)
            self.add_signal(-25_000_000, -25.0)
            self.add_signal(5_000_000, -30.0)

    def stop(self) -> None:
        """Stop the simulator."""
        self.running = False
        self.frame_index = 0

    def status(self) -> dict:
        """Return a stable status structure for the assistant/UI."""
        return {
            "active": self.running,
            "source": "simulator",
            "frame_index": self.frame_index,
            "signal_count": len(self.signals),
        }

    def generate_frame(self) -> np.ndarray:
        if not self.running:
            raise RuntimeError("Signal source is not running")
        noise_power = self._dbm_to_linear(self.config.noise_floor_db)
        noise_i = np.random.normal(0, np.sqrt(noise_power / 2), self.config.fft_size)
        noise_q = np.random.normal(0, np.sqrt(noise_power / 2), self.config.fft_size)
        iq_data = noise_i + 1j * noise_q
        time_samples = np.arange(self.config.fft_size) / self.config.sample_rate
        for signal in self.signals:
            signal_freq = self.config.center_frequency + signal.frequency_offset_hz
            signal_power = self._dbm_to_linear(signal.power_dbm)
            signal_amplitude = np.sqrt(signal_power)
            phase = 2 * np.pi * signal_freq * time_samples
            iq_data += signal_amplitude * np.exp(1j * phase)
        self.frame_index += 1
        return iq_data

    @staticmethod
    def _dbm_to_linear(power_dbm: float) -> float:
        return 10 ** ((power_dbm - 30) / 10)

    def get_signal_info(self) -> str:
        lines = ["Simulated signals:"]
        for sig in self.signals:
            freq_mhz = (self.config.center_frequency + sig.frequency_offset_hz) / 1e6
            direction = "above" if sig.frequency_offset_hz > 0 else "below"
            offset_mhz = abs(sig.frequency_offset_hz) / 1e6
            lines.append(f"  • {offset_mhz:.0f} MHz {direction} center @ {sig.power_dbm} dBm")
        return "\n".join(lines)
