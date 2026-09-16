"""Authenticated receive-only audio preview generation."""

from __future__ import annotations

import io
import wave

import numpy as np

from app.dsp.audio import demodulate


def build_audio_wav(service, mode: str, bandwidth_hz: float | None = None, audio_rate_hz: int = 48_000, preview_seconds: float = 0.25) -> bytes:
    """Demodulate the latest IQ capture into a browser-sized mono PCM preview."""
    iq, spectrum = service.latest_iq()
    if iq is None or not spectrum:
        raise ValueError("No RF capture is available for audio")
    sample_rate_hz = float(spectrum.get("sample_rate_hz", service.config.sample_rate))
    target_samples = max(2, int(round(sample_rate_hz * preview_seconds)))
    if iq.size < target_samples:
        repeats = int(np.ceil(target_samples / iq.size))
        iq = np.tile(iq, repeats)[:target_samples]
    else:
        iq = iq[:target_samples]
    audio = demodulate(iq, sample_rate_hz, mode, audio_rate_hz=audio_rate_hz, audio_bandwidth_hz=bandwidth_hz)
    audio = np.clip(np.asarray(audio, dtype=np.float32), -1.0, 1.0)
    pcm = (audio * 32767.0).astype("<i2").tobytes()
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(audio_rate_hz); wav.writeframes(pcm)
    return out.getvalue()
