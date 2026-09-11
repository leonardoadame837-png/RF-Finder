"""Passive multi-position RF localization helpers."""

from __future__ import annotations

import math


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def build_heatmap(observations: list[dict], *, frequency_tolerance_hz: float = 25_000.0) -> dict:
    """Build weighted receiver-position cells; never claims a transmitter location."""
    valid = [o for o in observations if o.get("latitude") is not None and o.get("longitude") is not None and not o.get("simulated")]
    cells = []
    for item in valid:
        freq = float(item.get("frequency_hz", 0.0))
        repeat = sum(1 for x in valid if abs(float(x.get("frequency_hz", 0.0)) - freq) <= frequency_tolerance_hz)
        snr = max(0.0, float(item.get("snr_db", 0.0)))
        cells.append({"latitude": float(item["latitude"]), "longitude": float(item["longitude"]), "weight": round(max(1.0, snr) * repeat, 3), "frequency_hz": freq, "observation_id": int(item.get("id", 0)), "timestamp": item.get("timestamp")})
    return {"schema_version": "1.0", "method": "repeated_receiver_position_heatmap", "measurement_count": len(valid), "cells": cells, "limitations": ["Cells represent receiver measurement positions, not proven transmitter coordinates.", "Multiple positions do not by themselves establish a transmitter location.", "Terrain, antenna pattern, propagation and receiver calibration affect received power.", "Simulated observations are excluded from localization."]}


def summarize_tracks(observations: list[dict], frequency_tolerance_hz: float = 25_000.0) -> list[dict]:
    """Group real observations into nearby-frequency passive measurement tracks."""
    real = [o for o in observations if not o.get("simulated") and o.get("latitude") is not None and o.get("longitude") is not None]
    groups: list[list[dict]] = []
    for obs in sorted(real, key=lambda x: float(x.get("frequency_hz", 0.0))):
        freq = float(obs.get("frequency_hz", 0.0))
        group = next((g for g in groups if abs(float(g[0].get("frequency_hz", 0.0)) - freq) <= frequency_tolerance_hz), None)
        if group is None:
            group = []
            groups.append(group)
        group.append(obs)
    return [{"frequency_hz": sum(float(x.get("frequency_hz", 0.0)) for x in group) / len(group), "measurement_count": len(group), "points": [{"latitude": float(x["latitude"]), "longitude": float(x["longitude"]), "observation_id": int(x.get("id", 0))} for x in group]} for group in groups]
