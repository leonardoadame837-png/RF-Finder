"""Authenticated receive-only audio preview generation."""

from __future__ import annotations

import io
import wave

import numpy as np

from app.dsp.audio import demodulate


MAX_PREVIEW_SECONDS = 2.0
MIN_PREVIEW_SECONDS = 0.01
MIN_AUDIO_RATE_HZ = 8_000
MAX_AUDIO_RATE_HZ = 192_000


def build_audio_wav(
    service,
    mode: str,
    bandwidth_hz: float | None = None,
    audio_rate_hz: int = 48_000,
    preview_seconds: float = 0.25,
) -> bytes:
    """Demodulate the latest IQ capture into a bounded browser-sized mono PCM preview."""
    if not np.isfinite(preview_seconds) or not MIN_PREVIEW_SECONDS <= preview_seconds <= MAX_PREVIEW_SECONDS:
        raise ValueError(f"preview_seconds must be between {MIN_PREVIEW_SECONDS} and {MAX_PREVIEW_SECONDS}")
    if not isinstance(audio_rate_hz, (int, np.integer)) or not MIN_AUDIO_RATE_HZ <= audio_rate_hz <= MAX_AUDIO_RATE_HZ:
        raise ValueError(f"audio_rate_hz must be between {MIN_AUDIO_RATE_HZ} and {MAX_AUDIO_RATE_HZ}")
    if bandwidth_hz is not None and (
        not np.isfinite(bandwidth_hz) or bandwidth_hz <= 0
    ):
        raise ValueError("bandwidth_hz must be finite and positive")

    iq, spectrum = service.latest_iq()
    if iq is None or not spectrum:
        raise ValueError("No RF capture is available for audio")
    sample_rate_hz = float(spectrum.get("sample_rate_hz", service.config.sample_rate))
    if not np.isfinite(sample_rate_hz) or sample_rate_hz <= 0:
        raise ValueError("RF sample rate must be finite and positive")
    if bandwidth_hz is not None and bandwidth_hz >= sample_rate_hz / 2:
        raise ValueError("bandwidth_hz must be below the RF Nyquist rate")

    target_samples = max(2, int(round(sample_rate_hz * preview_seconds)))
    if iq.size < target_samples:
        repeats = int(np.ceil(target_samples / iq.size))
        iq = np.tile(iq, repeats)[:target_samples]
    else:
        iq = iq[:target_samples]
    audio = demodulate(
        iq,
        sample_rate_hz,
        mode,
        audio_rate_hz=audio_rate_hz,
        audio_bandwidth_hz=bandwidth_hz,
    )
    audio = np.clip(np.asarray(audio, dtype=np.float32), -1.0, 1.0)
    pcm = (audio * 32767.0).astype("<i2").tobytes()
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(audio_rate_hz)
        wav.writeframes(pcm)
    return out.getvalue()
