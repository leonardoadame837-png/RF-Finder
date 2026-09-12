"""Portable imported-sample source abstraction."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass

import numpy as np

from app.source_types import SourceType


@dataclass(frozen=True)
class ImportedIQ:
    samples: np.ndarray
    center_frequency_hz: float
    sample_rate_hz: float
    timestamp: str | None
    sample_format: str
    source_type: SourceType = SourceType.IMPORTED_MEASUREMENT


def parse_imported_samples(payload: str | bytes, filename: str = "samples.json") -> ImportedIQ:
    """Parse JSON or CSV complex samples; no hardware origin is inferred."""
    text = payload.decode("utf-8") if isinstance(payload, bytes) else payload
    if filename.lower().endswith(".csv"):
        reader = csv.DictReader(io.StringIO(text))
        values = []
        for row in reader:
            real = float(row.get("real", row.get("i", "0")))
            imag = float(row.get("imag", row.get("q", "0")))
            values.append(real + 1j * imag)
        metadata = {}
        samples = np.asarray(values, dtype=np.complex128)
    else:
        obj = json.loads(text)
        metadata = obj if isinstance(obj, dict) else {}
        raw = obj.get("samples", obj.get("iq", [])) if isinstance(obj, dict) else obj
        if raw and isinstance(raw[0], dict):
            samples = np.asarray([float(v.get("real", v.get("i", 0))) + 1j * float(v.get("imag", v.get("q", 0))) for v in raw], dtype=np.complex128)
        else:
            samples = np.asarray(raw, dtype=np.complex128)
    if samples.size == 0 or not np.all(np.isfinite(samples.real)) or not np.all(np.isfinite(samples.imag)):
        raise ValueError("Imported samples must be non-empty and finite")
    return ImportedIQ(
        samples=samples,
        center_frequency_hz=float(metadata.get("center_frequency_hz", 0)),
        sample_rate_hz=float(metadata.get("sample_rate_hz", 0)),
        timestamp=metadata.get("timestamp"),
        sample_format=str(metadata.get("sample_format", "complex128")),
        source_type=SourceType(metadata.get("source_type", SourceType.IMPORTED_MEASUREMENT.value)),
    )
