#!/usr/bin/env python3
"""RF Finder - Stage 1: Software-only prototype with local authentication."""

import sys
from app.auth import AuthManager, first_run_setup, login_prompt
from app.config import default_config
from app.sources.simulator import SignalSimulator
from app.dsp.analyzer import SpectrumAnalyzer
from app.dsp.detector import SignalDetector


def format_frequency(freq_hz: float) -> str:
    """Format frequency in human-readable form."""
    if freq_hz >= 1e9:
        return f"{freq_hz / 1e9:.2f} GHz"
    if freq_hz >= 1e6:
        return f"{freq_hz / 1e6:.2f} MHz"
    if freq_hz >= 1e3:
        return f"{freq_hz / 1e3:.2f} kHz"
    return f"{freq_hz:.0f} Hz"


def main() -> int:
    """Authenticate the local user, then run the RF Finder pipeline."""
    auth = AuthManager()
    if not auth.has_account():
        first_run_setup(auth)
    session = login_prompt(auth)

    print("=" * 70)
    print("RF FINDER — Stage 1: Software-only Prototype")
    print("=" * 70)
    print(f"Authenticated user: {session.user.username} ({session.user.role})")
    print("Session token: issued in memory; expires after 1 hour")
    print()

    print("Configuration:")
    print(f"  Source: {default_config.source}")
    print(f"  Sample Rate: {default_config.sample_rate / 1e6:.1f} MS/s")
    print(f"  Center Frequency: {format_frequency(default_config.center_frequency)}")
    print(f"  FFT Size: {default_config.fft_size}")
    print(f"  Detection Threshold: {default_config.detection_threshold_db:.1f} dB above noise")
    print()

    print("Initializing signal source...")
    simulator = SignalSimulator(default_config)
    simulator.start()
    print("Signal source initialized.")
    print(f"  {simulator.get_signal_info()}")
    print()

    print("Initializing DSP pipeline...")
    analyzer = SpectrumAnalyzer(default_config)
    detector = SignalDetector(default_config)
    print("DSP pipeline ready.")
    freq_res = analyzer.get_frequency_resolution()
    print(f"  Frequency resolution: {freq_res / 1e3:.1f} kHz")
    print()

    print(f"Processing {default_config.num_frames} RF frames...")
    print("-" * 70)
    try:
        for frame_num in range(1, default_config.num_frames + 1):
            iq_data = simulator.generate_frame()
            frequencies, power_spectrum, noise_floor = analyzer.analyze(iq_data)
            detections = detector.detect(frequencies, power_spectrum, noise_floor, frame_num)

            print(f"Frame {frame_num}:")
            print(f"  Noise Floor: {noise_floor:.1f} dB")
            print(f"  Detected Signals: {len(detections)}")
            for i, det in enumerate(detections, 1):
                print(
                    f"    [{i}] {format_frequency(det.center_frequency_hz)} | "
                    f"Power: {det.peak_power_db:.1f} dB | "
                    f"SNR: {det.snr_db:.1f} dB | "
                    f"BW: {det.bandwidth_hz / 1e3:.1f} kHz"
                )
            if frame_num < default_config.num_frames:
                print()
    finally:
        simulator.stop()
        auth.logout(session.token)

    print("-" * 70)
    print("\nProcessing complete. Session closed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
