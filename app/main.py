#!/usr/bin/env python3
"""RF Finder - Stage 1: Software-only prototype.

Main entry point for the RF signal detection and analysis application.
"""

import sys
from app.config import default_config
from app.sources.simulator import SignalSimulator
from app.dsp.analyzer import SpectrumAnalyzer
from app.dsp.detector import SignalDetector


def format_frequency(freq_hz: float) -> str:
    """Format frequency in human-readable form."""
    if freq_hz >= 1e9:
        return f"{freq_hz / 1e9:.2f} GHz"
    elif freq_hz >= 1e6:
        return f"{freq_hz / 1e6:.2f} MHz"
    elif freq_hz >= 1e3:
        return f"{freq_hz / 1e3:.2f} kHz"
    else:
        return f"{freq_hz:.0f} Hz"


def main():
    """Run the RF Finder application."""
    print("=" * 70)
    print("RF FINDER — Stage 1: Software-only Prototype")
    print("=" * 70)
    
    # Display configuration
    print("Configuration:")
    print(f"  Source: {default_config.source}")
    print(f"  Sample Rate: {default_config.sample_rate / 1e6:.1f} MS/s")
    print(f"  Center Frequency: {format_frequency(default_config.center_frequency)}")
    print(f"  FFT Size: {default_config.fft_size}")
    print(f"  Detection Threshold: {default_config.detection_threshold_db:.1f} dB above noise")
    print()
    
    # Initialize signal source
    print("Initializing signal source...")
    simulator = SignalSimulator(default_config)
    simulator.start()
    print("Signal source initialized.")
    print(f"  {simulator.get_signal_info()}")
    print()
    
    # Initialize DSP pipeline
    print("Initializing DSP pipeline...")
    analyzer = SpectrumAnalyzer(default_config)
    detector = SignalDetector(default_config)
    print("DSP pipeline ready.")
    freq_res = analyzer.get_frequency_resolution()
    print(f"  Frequency resolution: {freq_res / 1e3:.1f} kHz")
    print()
    
    # Process frames
    print(f"Processing {default_config.num_frames} RF frames...")
    print("-" * 70)
    
    for frame_num in range(1, default_config.num_frames + 1):
        # Generate frame
        iq_data = simulator.generate_frame()
        
        # Analyze spectrum
        frequencies, power_spectrum, noise_floor = analyzer.analyze(iq_data)
        
        # Detect signals
        detections = detector.detect(frequencies, power_spectrum, noise_floor, frame_num)
        
        # Display results
        print(f"Frame {frame_num}:")
        print(f"  Noise Floor: {noise_floor:.1f} dB")
        print(f"  Detected Signals: {len(detections)}")
        
        for i, det in enumerate(detections, 1):
            print(f"    [{i}] {format_frequency(det.center_frequency_hz)} | "
                  f"Power: {det.peak_power_db:.1f} dB | "
                  f"SNR: {det.snr_db:.1f} dB | "
                  f"BW: {det.bandwidth_hz / 1e3:.1f} kHz")
        
        if frame_num < default_config.num_frames:
            print()
    
    print("-" * 70)
    print("\nProcessing complete.")
    simulator.stop()


if __name__ == "__main__":
    sys.exit(main())
