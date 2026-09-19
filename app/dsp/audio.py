"""Receive-only audio demodulation helpers for authorized RF signals."""

from __future__ import annotations

import numpy as np
from scipy import signal

SUPPORTED_MODES = ("am", "fm", "nfm", "wfm")


def _validate_iq(iq: np.ndarray) -> np.ndarray:
    samples = np.asarray(iq, dtype=np.complex128).reshape(-1)
    if samples.size < 2:
        raise ValueError("IQ input must contain at least two samples")
    if not np.all(np.isfinite(samples.real)) or not np.all(np.isfinite(samples.imag)):
        raise ValueError("IQ input must contain only finite values")
    return samples


def _lowpass(samples: np.ndarray, sample_rate_hz: float, cutoff_hz: float) -> np.ndarray:
    if not np.isfinite(sample_rate_hz) or sample_rate_hz <= 0:
        raise ValueError("sample_rate_hz must be finite and positive")
    if not np.isfinite(cutoff_hz) or cutoff_hz <= 0 or cutoff_hz >= sample_rate_hz / 2:
        raise ValueError("cutoff_hz must be between 0 and Nyquist")
    sos = signal.butter(6, cutoff_hz, btype="lowpass", fs=sample_rate_hz, output="sos")
    return signal.sosfilt(sos, samples)


def _resample(audio: np.ndarray, input_rate_hz: float, output_rate_hz: int) -> np.ndarray:
    if output_rate_hz <= 0 or input_rate_hz <= 0:
        raise ValueError("sample rates must be positive")
    if audio.size == 0 or np.isclose(input_rate_hz, output_rate_hz):
        return np.clip(audio, -1.0, 1.0).astype(np.float32, copy=False)
    target = max(1, int(round(audio.size * output_rate_hz / input_rate_hz)))
    resampled = signal.resample(audio, target)
    return np.clip(resampled, -1.0, 1.0).astype(np.float32)


def demodulate_am(
    iq: np.ndarray,
    sample_rate_hz: float,
    *,
    audio_rate_hz: int = 48_000,
    audio_bandwidth_hz: float = 10_000,
) -> np.ndarray:
    """Envelope-demodulate a conventional AM signal into normalized mono audio."""
    samples = _validate_iq(iq)
    audio = _lowpass(
        np.abs(samples) - np.mean(np.abs(samples)),
        sample_rate_hz,
        min(audio_bandwidth_hz, sample_rate_hz * 0.45),
    )
    audio = _resample(audio, sample_rate_hz, audio_rate_hz)
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak > 0:
        audio = audio / peak
    return audio.astype(np.float32, copy=False)


def demodulate_fm(
    iq: np.ndarray,
    sample_rate_hz: float,
    *,
    audio_rate_hz: int = 48_000,
    audio_bandwidth_hz: float = 15_000,
) -> np.ndarray:
    """Phase-difference FM demodulation into normalized mono audio."""
    samples = _validate_iq(iq)
    audio = np.diff(np.unwrap(np.angle(samples))) * sample_rate_hz / (2.0 * np.pi)
    audio = _lowpass(
        audio,
        sample_rate_hz,
        min(float(audio_bandwidth_hz), sample_rate_hz * 0.45),
    )
    audio = _resample(audio, sample_rate_hz, audio_rate_hz)
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak > 0:
        audio = audio / peak
    return audio.astype(np.float32, copy=False)


def demodulate(
    iq: np.ndarray,
    sample_rate_hz: float,
    mode: str,
    *,
    audio_rate_hz: int = 48_000,
    audio_bandwidth_hz: float | None = None,
) -> np.ndarray:
    """Dispatch AM/FM-family demodulation using an explicit receive mode."""
    normalized = str(mode).lower()
    if normalized not in SUPPORTED_MODES:
        raise ValueError(f"Unsupported demodulation mode: {mode!r}")
    if normalized == "am":
        return demodulate_am(
            iq,
            sample_rate_hz,
            audio_rate_hz=audio_rate_hz,
            audio_bandwidth_hz=10_000 if audio_bandwidth_hz is None else audio_bandwidth_hz,
        )
    bandwidth = 15_000 if normalized in {"fm", "wfm"} else 5_000
    return demodulate_fm(
        iq,
        sample_rate_hz,
        audio_rate_hz=audio_rate_hz,
        audio_bandwidth_hz=bandwidth if audio_bandwidth_hz is None else audio_bandwidth_hz,
    )
