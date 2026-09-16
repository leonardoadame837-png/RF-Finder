import numpy as np

from app.dsp.signal_classification import classify_iq


def test_insufficient_iq_is_unknown():
    result = classify_iq(np.ones(16, dtype=np.complex128), 200_000)
    assert result.label == "unknown"
    assert result.confidence == 0.0


def test_finite_digital_like_block_is_classified_with_evidence():
    rng = np.random.default_rng(42)
    iq = (rng.normal(size=4096) + 1j * rng.normal(size=4096)).astype(np.complex128)
    result = classify_iq(iq, 2_000_000)
    assert result.label in {"digital", "likely-encrypted", "unknown"}
    assert 0.0 <= result.confidence <= 1.0
    assert "spectral_entropy" in result.evidence
    assert "digital_score" in result.evidence


def test_nonfinite_iq_is_rejected():
    iq = np.ones(128, dtype=np.complex128)
    iq[3] = np.nan + 0j
    try:
        classify_iq(iq, 200_000)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "finite" in str(exc)
