"""Authenticated live RF frames for the field UI."""
from fastapi import APIRouter, Header, HTTPException
import numpy as np

from app.auth.permissions import has_permission
from app.api.server import current_user
from app.config import default_config
from app.dsp.analyzer import SpectrumAnalyzer
from app.dsp.detector import SignalDetector
from app.sources.simulator import SignalSimulator

router = APIRouter(prefix="/live", tags=["live"])
analyzer = SpectrumAnalyzer(default_config)
detector = SignalDetector(default_config)
simulator = SignalSimulator(default_config)


def authorized(authorization: str | None):
    user = current_user(authorization)
    if not has_permission(user.role, "measurements:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return user


@router.get("/status")
def status(authorization: str | None = Header(default=None)):
    authorized(authorization)
    return {"running": True, "source": "simulator", "mode": "live-dsp"}


@router.get("/frame")
def frame(authorization: str | None = Header(default=None)):
    authorized(authorization)
    iq = np.asarray(simulator.generate_frame())
    frequencies, spectrum, noise_floor = analyzer.analyze(iq)
    detections = detector.detect(frequencies, spectrum, noise_floor)
    return {
        "center_frequency_hz": default_config.center_frequency,
        "sample_rate_hz": default_config.sample_rate,
        "frequencies_hz": frequencies.tolist(),
        "power_db": spectrum.tolist(),
        "noise_floor_db": float(noise_floor),
        "detections": [d.__dict__ for d in detections],
    }
