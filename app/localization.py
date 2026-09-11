"""Passive multi-position RF localization helpers.

This module estimates a probable observation area from receiver GPS samples.
It never claims an exact transmitter location or legal status.
"""

from __future__ import annotations

import math
from collections import defaultdict


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def build_heatmap(observations: list[dict], *, frequency_tolerance_hz: float = 25_000.0) -> dict:
    """Return weighted receiver-position cells for repeated passive observations.

    Weight increases with SNR and repetition. The result is an observation heatmap,
    not a triangulated transmitter position.
    """
    valid = [o for o in observations if o.get("latitude") is not None and o.get("longitude") is not None and not o.get("simulated")]
    cells: list[dict] = []
    for item in valid:
        freq = float(item.get("frequency_hz", 0.0))
        group = [x for x in valid if abs(float(x.get("frequency_hz", 0.0)) - freq) <= frequency_tolerance_hz]
        snr = max(0.0, float(item.get("snr_db", 0.0)))
        repeat = len(group)
        weight = max(1.0, snr) * repeat
        cells.append({"latitude": float(item["latitude"]), "longitude": float(item["longitude"]), "weight": round(weight, 3), "frequency_hz": freq, "observation_id": int(item.get("id", 0)), "timestamp": item.get("timestamp")})
    return {
        "schema_version": "1.0",
        "method": "repeated_receiver_position_heatmap",
        "measurement_count": len(valid),
        "cells": cells,
        "limitations": [
            "Cells represent receiver measurement positions, not proven transmitter coordinates.",
            "Multiple positions do not by themselves establish a transmitter location.",
            "Terrain, antenna pattern, propagation and receiver calibration affect received power.",
            "Simulated observations are excluded from localization.",
        ],
    }


def summarize_tracks(observations: list[dict], frequency_tolerance_hz: float = 25_000.0) -> list[dict]:
    """Group nearby-frequency observations into passive measurement tracks."""
    real = [o for o in observations if not o.get("simulated") and o.get("latitude") is not None and o.get("longitude") is not None]
    groups: list[list[dict]] = []
    for obs in sorted(real, key=lambda x: float(x.get("frequency_hz", 0.0))):
        freq = float(obs.get("frequency_hz", 0.0))
        target = next((g for g in groups if abs(float(g[0].get("frequency_hz", 0.0)) - freq) <= frequency_tolerance_hz), None)
        (target if target is not None else groups.append([obs]) or groups[-1]).append(obs) if target is not None else None
    tracks = []
    for group in groups:
        points = [{"latitude": float(x["latitude"]), "longitude": float(x["longitude"]), "observation_id": int(x.get("id", 0))} for x in group]
        tracks.append({"frequency_hz": sum(float(x.get("frequency_hz", 0.0)) for x in group) / len(group), "measurement_count": len(group), "points": points})
    return tracks
