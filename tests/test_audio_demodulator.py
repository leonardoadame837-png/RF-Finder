"""Software-only tests for receive-only audio demodulation."""

import numpy as np
import pytest

from app.dsp.audio import SUPPORTED_MODES, demodulate, demodulate_am, demodulate_fm


def _am_iq(sample_rate=192_000, duration=0.08, audio_hz=1_000, carrier_hz=20_000):
    t = np.arange(int(sample_rate * duration)) / sample_rate
    modulation = 0.55 * np.sin(2 * np.pi * audio_hz * t)
    return (1.0 + modulation) * np.exp(1j * 2 * np.pi * carrier_hz * t)


def _fm_iq(sample_rate=192_000, duration=0.08, audio_hz=1_000, deviation_hz=8_000):
    t = np.arange(int(sample_rate * duration)) / sample_rate
    phase = 2 * np.pi * deviation_hz * np.sin(2 * np.pi * audio_hz * t) / sample_rate
    phase = np.cumsum(phase)
    return np.exp(1j * 2 * np.pi * 20_000 * t) * np.exp(1j * phase)


def test_am_demodulator_returns_normalized_audio():
    audio = demodulate_am(_am_iq(), 192_000, audio_rate_hz=48_000)
    assert audio.dtype == np.float32
    assert audio.size > 1_000
    assert np.max(np.abs(audio)) <= 1.001
    assert np.std(audio) > 0.01


def test_fm_demodulator_returns_normalized_audio():
    audio = demodulate_fm(_fm_iq(), 192_000, audio_rate_hz=48_000)
    assert audio.dtype == np.float32
    assert audio.size > 1_000
    assert np.max(np.abs(audio)) <= 1.001
    assert np.std(audio) > 0.01


def test_dispatch_supports_fm_family_modes():
    iq = _fm_iq()
    for mode in SUPPORTED_MODES:
        audio = demodulate(iq, 192_000, mode, audio_rate_hz=24_000)
        assert audio.size > 500
        assert np.all(np.isfinite(audio))


def test_unknown_demodulation_mode_is_rejected():
    with pytest.raises(ValueError, match="Unsupported demodulation mode"):
        demodulate(_am_iq(), 192_000, "encrypted")
