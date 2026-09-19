"""Conservative RF signal classification heuristics.

These features can identify signals that look digitally modulated or unusually
noise-like, but RF observations alone cannot prove that a transmission is
encrypted. No key recovery or protected-content decryption is performed here.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class SignalClassification:
    """Classification result with machine-readable evidence."""

    label: str
    confidence: float
    evidence: dict[str, float | str]

    def to_dict(self) -> dict:
        return asdict(self)


def classify_iq(iq: np.ndarray, sample_rate_hz: float) -> SignalClassification:
    """Classify an IQ block as unknown/digital/likely-encrypted.

    This is a triage heuristic, not a cryptographic detector. In particular,
    ``likely-encrypted`` means the observed signal has characteristics commonly
    associated with digital/noise-like traffic; it does not establish that
    encryption is present.
    """
    samples = np.asarray(iq, dtype=np.complex128).reshape(-1)
    if samples.size < 32:
        return SignalClassification("unknown", 0.0, {"reason": "insufficient_samples"})
    if not np.isfinite(samples.real).all() or not np.isfinite(samples.imag).all():
        raise ValueError("IQ samples must be finite")
    if sample_rate_hz <= 0:
        raise ValueError("sample_rate_hz must be positive")

    window = np.hanning(samples.size)
    spectrum = np.abs(np.fft.fftshift(np.fft.fft(samples * window))) ** 2
    spectrum = np.maximum(spectrum, np.finfo(float).tiny)
    probability = spectrum / spectrum.sum()
    entropy = float(-(probability * np.log2(probability)).sum() / np.log2(probability.size))
    peak_to_median_db = float(10.0 * np.log10(np.max(spectrum) / np.median(spectrum)))

    magnitude = np.abs(samples)
    mean_mag = float(np.mean(magnitude))
    rms_mag = float(np.sqrt(np.mean(magnitude**2)))
    crest = rms_mag / max(mean_mag, np.finfo(float).eps)
    centered = magnitude - mean_mag
    transitions = float(np.mean(np.abs(np.diff(np.signbit(centered))))) if magnitude.size > 1 else 0.0

    # Broad, noise-like occupied energy plus low spectral prominence is a useful
    # triage signal for digital traffic. Thresholds are intentionally conservative.
    digital_score = 0.45 * entropy + 0.30 * min(transitions * 2.0, 1.0) + 0.25 * min(crest / 2.0, 1.0)
    if digital_score >= 0.68 and entropy >= 0.78:
        label = "likely-encrypted"
        confidence = min(0.95, 0.55 + 0.40 * digital_score)
    elif digital_score >= 0.50:
        label = "digital"
        confidence = min(0.90, 0.45 + 0.45 * digital_score)
    else:
        label = "unknown"
        confidence = min(0.60, 0.20 + 0.40 * digital_score)

    return SignalClassification(
        label,
        float(confidence),
        {
            "spectral_entropy": entropy,
            "peak_to_median_db": peak_to_median_db,
            "magnitude_crest_factor": float(crest),
            "magnitude_transition_rate": transitions,
            "digital_score": float(digital_score),
            "sample_rate_hz": float(sample_rate_hz),
        },
    )
