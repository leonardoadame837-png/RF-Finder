#!/usr/bin/env python3
"""RF Finder - Stage 1: Software-only prototype with local authentication."""

import os
import sys
from app.auth import AuthManager, first_run_setup, login_prompt
from app.config import default_config
from app.sources.simulator import SignalSimulator
from app.dsp.analyzer import SpectrumAnalyzer
from app.dsp.detector import SignalDetector
from app.observation import RFObservation, classify_observation
from app.storage import ObservationStore


def format_frequency(freq_hz: float) -> str:
    """Format frequency in human-readable form."""
    if freq_hz >= 1e9:
        return f"{freq_hz / 1e9:.2f} GHz"
    if freq_hz >= 1e6:
        return f"{freq_hz / 1e6:.2f} MHz"
    if freq_hz >= 1e3:
        return f"{freq_hz / 1e3:.2f} kHz"
    return f"{freq_hz:.0f} Hz"


def _gps_from_environment():
    """Read optional receiver coordinates without pretending the simulator has GPS."""
    try:
        lat = float(os.getenv("RF_FINDER_LAT", ""))
        lon = float(os.getenv("RF_FINDER_LON", ""))
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError
        alt = float(os.getenv("RF_FINDER_ALT_M", "0"))
        return lat, lon, alt
    except (TypeError, ValueError):
        return None, None, None


def main() -> int:
    """Authenticate the local user, run the RF pipeline, and persist observations."""
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
    store = ObservationStore(default_config.database_path)
    lat, lon, alt = _gps_from_environment()
    print("DSP pipeline ready.")
    print(f"  Frequency resolution: {analyzer.get_frequency_resolution() / 1e3:.1f} kHz")
    print(f"  Receiver position: {'configured' if lat is not None else 'not configured'}")
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
                observation = classify_observation(RFObservation.now(
                    frequency_hz=det.center_frequency_hz,
                    peak_power_db=det.peak_power_db,
                    noise_floor_db=noise_floor,
                    snr_db=det.snr_db,
                    bandwidth_hz=det.bandwidth_hz,
                    latitude=lat,
                    longitude=lon,
                    altitude_m=alt,
                    source=default_config.source,
                    evidence="simulated_signal" if default_config.source == "simulator" else "",
                    simulated=default_config.source == "simulator",
                ))
                store.add(observation)
                print(
                    f"    [{i}] {format_frequency(det.center_frequency_hz)} | "
                    f"Power: {det.peak_power_db:.1f} dB | "
                    f"SNR: {det.snr_db:.1f} dB | "
                    f"BW: {det.bandwidth_hz / 1e3:.1f} kHz | "
                    f"Class: {observation.signal_class}"
                )
            if frame_num < default_config.num_frames:
                print()
    finally:
        simulator.stop()
        auth.logout(session.token)

    print("-" * 70)
    print(f"\nProcessing complete. Observations saved to {default_config.database_path}.")
    print("Run `python -m app.tactical_server` to open the tactical map.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
