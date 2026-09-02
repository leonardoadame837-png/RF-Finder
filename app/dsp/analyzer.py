"""FFT-based Spectrum Analyzer."""

import numpy as np
from scipy import signal
from typing import Tuple


class SpectrumAnalyzer:
    """Performs FFT-based spectrum analysis on RF signals."""
    
    def __init__(self, config):
        """Initialize the spectrum analyzer.
        
        Args:
            config: Config object with fft_size, sample_rate, center_frequency
        """
        self.config = config
        self.window = signal.windows.hamming(config.fft_size)
    
    def analyze(self, iq_data: np.ndarray) -> Tuple[np.ndarray, np.ndarray, float]:
        """Perform FFT analysis on IQ data.
        
        Args:
            iq_data: Complex numpy array of IQ samples
            
        Returns:
            Tuple of:
            - frequencies: Array of frequency values (Hz)
            - power_spectrum: Power in dB (20 * log10(magnitude))
            - noise_floor: Estimated noise floor in dB
        """
        # Apply window
        windowed = iq_data * self.window
        
        # Compute FFT and shift so DC is centered
        fft_result = np.fft.fft(windowed)
        fft_shifted = np.fft.fftshift(fft_result)
        magnitude = np.abs(fft_shifted)
        
        # Convert to power (dB)
        # Avoid log(0) by adding small epsilon
        epsilon = 1e-10
        power_linear = (magnitude ** 2) / self.config.fft_size
        power_db = 10 * np.log10(power_linear + epsilon)
        
        # Compute frequency axis (centered around center_frequency)
        freq_bins = np.fft.fftfreq(self.config.fft_size, 1 / self.config.sample_rate)
        frequencies = self.config.center_frequency + np.fft.fftshift(freq_bins)
        
        # Estimate noise floor (5th percentile to ensure it's below most values)
        noise_floor = np.percentile(power_db, 5)
        
        return frequencies, power_db, noise_floor
    
    def get_frequency_resolution(self) -> float:
        """Get the frequency resolution in Hz.
        
        Returns:
            Frequency resolution (Hz per bin)
        """
        return self.config.sample_rate / self.config.fft_size
