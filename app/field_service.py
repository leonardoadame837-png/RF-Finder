"""Continuous RF field service tying source, DSP, persistence and UI state together."""

from __future__ import annotations

import json
import os
import platform
import threading
import time
from collections import deque
from datetime import datetime, timezone

import numpy as np

from app.ai_spectrum_agent import LocalSpectrumAnalyst, build_agent_context
from app.config import default_config
from app.device_telemetry import TelemetryStore
from app.dsp.analyzer import SpectrumAnalyzer
from app.dsp.detector import SignalDetector
from app.dsp.signal_classification import classify_iq
from app.observation import RFObservation, classify_observation
from app.sources.base import source_provenance
from app.sources.simulator import SignalSimulator
from app.sources.types import SourceType, normalize_source_type
from app.storage import ObservationStore


class RFService:
    """Continuous cross-platform RF monitoring service."""

    def __init__(self, config=default_config, source=None, scan_interval_s: float = 0.5):
        self.config = config
        self.source = source or self._build_source(config)
        self.analyzer = SpectrumAnalyzer(config)
        self.detector = SignalDetector(config)
        self.store = ObservationStore(config.database_path)
        self.telemetry = TelemetryStore()
        self.agent = LocalSpectrumAnalyst()
        self.scan_interval_s = max(0.05, float(scan_interval_s))
        self._thread: threading.Thread | None = None
        self._stop = threading.Event(); self._lock = threading.RLock(); self._running = False
        self._frame_index = 0; self._last_error: str | None = None; self._latest = None
        self._latest_iq: np.ndarray | None = None
        self._latest_detections = []; self._waterfall = deque(maxlen=config.waterfall_history_frames)
        self._last_scan_at: str | None = None
        self._lat = self._env_float("RF_FINDER_LAT"); self._lon = self._env_float("RF_FINDER_LON"); self._alt = self._env_float("RF_FINDER_ALT_M")

    @staticmethod
    def _build_source(config):
        mode = str(config.source).lower()
        if mode == "simulator": return SignalSimulator(config)
        if mode == "sdr":
            from app.sources.sdr import RTLSDRSource
            return RTLSDRSource(config, device_index=config.sdr_device_index, gain=config.sdr_gain)
        if mode == "network_sdr":
            from app.sources.network import RTLTCPSource
            return RTLTCPSource(config, host=config.network_sdr_host, port=config.network_sdr_port, timeout_s=config.network_sdr_timeout_s)
        raise ValueError(f"Unsupported RF source: {config.source!r}. Use simulator, sdr, or network_sdr.")

    @staticmethod
    def _env_float(name):
        value = os.getenv(name); return float(value) if value not in (None, "") else None

    @property
    def source_name(self) -> str:
        return getattr(self.source, "status", lambda: {"source": "unknown"})().get("source", "unknown")

    @property
    def source_type(self) -> SourceType:
        return normalize_source_type(source_provenance(self.source)["source_type"])

    def _capture_metadata(self) -> dict:
        status = self.source.status() if hasattr(self.source, "status") else {}
        return {"timestamp": status.get("last_timestamp"), "center_frequency_hz": status.get("center_frequency_hz", self.config.center_frequency), "sample_rate_hz": status.get("sample_rate_hz", self.config.sample_rate)}

    def start(self) -> None:
        with self._lock:
            if self._running: return
            self.source.start(); self._stop.clear(); self._running = True; self._last_error = None
        try: self.scan_once()
        except Exception as exc:
            with self._lock:
                source_frame = getattr(self.source, "frame_index", self._frame_index); self._frame_index = max(self._frame_index, int(source_frame)); self._last_error = f"{type(exc).__name__}: {exc}"
        with self._lock:
            if self._running:
                self._thread = threading.Thread(target=self._run, name="rf-finder-scan", daemon=True); self._thread.start()

    def stop(self) -> None:
        with self._lock: self._stop.set(); self._running = False
        if self._thread and self._thread.is_alive(): self._thread.join(timeout=max(1.0, self.scan_interval_s * 3))
        try: self.source.stop()
        except Exception: pass

    def _run(self) -> None:
        while not self._stop.is_set():
            started = time.monotonic()
            try: self.scan_once()
            except Exception as exc:
                with self._lock:
                    source_frame = getattr(self.source, "frame_index", self._frame_index); self._frame_index = max(self._frame_index, int(source_frame)); self._last_error = f"{type(exc).__name__}: {exc}"
            delay = self.scan_interval_s - (time.monotonic() - started)
            if delay > 0: self._stop.wait(delay)

    def _process_iq(self, iq, source_type: SourceType, timestamp: str | None = None, center_frequency_hz: float | None = None, sample_rate_hz: float | None = None) -> tuple[dict, list, dict]:
        frequencies, power, noise_floor = self.analyzer.analyze(iq, center_frequency_hz=center_frequency_hz, sample_rate_hz=sample_rate_hz)
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        detections = self.detector.detect(frequencies, power, noise_floor, self._frame_index + 1, source_type=source_type, timestamp=ts)
        classification = classify_iq(iq, float(sample_rate_hz if sample_rate_hz is not None else self.config.sample_rate))
        spectrum = {"timestamp": ts, "frequencies_hz": [float(x) for x in frequencies.tolist()], "power_db": [float(x) for x in power.tolist()], "noise_floor_db": float(noise_floor), "center_frequency_hz": float(center_frequency_hz if center_frequency_hz is not None else self.config.center_frequency), "sample_rate_hz": float(sample_rate_hz if sample_rate_hz is not None else self.config.sample_rate), "source_type": source_type.value, "provenance": {"source_type": source_type.value, "simulated": source_type is SourceType.SIMULATED, "verified_rf": source_type in {SourceType.IMPORTED_MEASUREMENT, SourceType.LIVE_MEASUREMENT}}, "signal_classification": classification.to_dict(), "detections": [d.to_dict() for d in detections]}
        return spectrum, detections, classification.to_dict()

    def _persist_detections(self, spectrum: dict, detections: list, classification: dict) -> None:
        for detection in detections:
            observation = RFObservation(timestamp=spectrum["timestamp"], frequency_hz=detection.center_frequency_hz, peak_power_db=detection.peak_power_db, noise_floor_db=detection.noise_floor_db, snr_db=detection.snr_db, bandwidth_hz=detection.bandwidth_hz, latitude=self._lat, longitude=self._lon, altitude_m=self._alt, source=self.source_name, source_type=detection.source_type, signal_class=classification["label"], confidence=detection.confidence, evidence="simulated_signal" if detection.source_type == SourceType.SIMULATED.value else "rf_measurement", classification_evidence=json.dumps({**classification["evidence"], "classification_confidence": classification["confidence"]}, sort_keys=True), encryption_status=classification["label"])
            stored = classify_observation(observation)
            if classification["label"] in {"digital", "likely-encrypted"}:
                stored.signal_class = classification["label"]
            # Classification is heuristic triage data; detector confidence remains
            # the independent measurement confidence used for the observation.
            self.store.add(stored)

    def scan_once(self) -> dict:
        iq = np.asarray(self.source.generate_frame(), dtype=np.complex128).reshape(-1)
        frame_index = getattr(self.source, "frame_index", self._frame_index + 1)
        metadata = self._capture_metadata()
        spectrum, detections, classification = self._process_iq(iq, self.source_type, metadata["timestamp"], metadata["center_frequency_hz"], metadata["sample_rate_hz"])
        with self._lock:
            self._frame_index = int(frame_index); self._latest = spectrum; self._latest_iq = iq.copy(); self._latest_detections = [d.to_dict() for d in detections]
            self._waterfall.append(spectrum["power_db"]); self._last_scan_at = spectrum["timestamp"]
        self._persist_detections(spectrum, detections, classification)
        return {"frame_index": frame_index, "detections": len(detections), "noise_floor_db": spectrum["noise_floor_db"], "signal_classification": classification}

    def ingest_imported(self, iq, metadata: dict | None = None) -> dict:
        metadata = metadata or {}
        source_type = normalize_source_type(metadata.get("source_type", SourceType.IMPORTED_MEASUREMENT.value))
        if source_type is SourceType.SIMULATED: raise ValueError("Imported measurement cannot be labeled SIMULATED")
        if source_type is SourceType.UNKNOWN: source_type = SourceType.IMPORTED_MEASUREMENT
        center = float(metadata.get("center_frequency_hz", self.config.center_frequency)); rate = float(metadata.get("sample_rate_hz", self.config.sample_rate))
        samples = np.asarray(iq, dtype=np.complex128).reshape(-1)
        spectrum, detections, classification = self._process_iq(samples, source_type, metadata.get("timestamp"), center, rate); spectrum["sample_format"] = str(metadata.get("sample_format", "complex64"))
        with self._lock:
            self._latest = spectrum; self._latest_iq = samples.copy(); self._latest_detections = [d.to_dict() for d in detections]; self._waterfall.append(spectrum["power_db"]); self._last_scan_at = spectrum["timestamp"]
        self._persist_detections(spectrum, detections, classification); return spectrum

    def latest_iq(self) -> tuple[np.ndarray | None, dict]:
        with self._lock:
            return (None if self._latest_iq is None else self._latest_iq.copy(), dict(self._latest) if self._latest else {})

    def update_telemetry(self, payload: dict) -> dict: return self.telemetry.update(payload)
    def spectrum_agent_analysis(self) -> dict: return self.agent.analyze(build_agent_context(self.latest_spectrum(), self.observations(limit=30)))

    def status(self) -> dict:
        with self._lock:
            source_status = self.source.status() if hasattr(self.source, "status") else {}; provenance = source_provenance(self.source)
            return {"running": self._running, "platform": platform.system().lower(), "client_architecture": "browser + local RF service", "source": self.source_name, "source_status": source_status, "provenance": provenance, "source_type": provenance["source_type"], "frame_index": self._frame_index, "last_scan_at": self._last_scan_at, "last_error": self._last_error, "center_frequency_hz": source_status.get("center_frequency_hz", self.config.center_frequency), "sample_rate_hz": source_status.get("sample_rate_hz", self.config.sample_rate), "fft_size": self.config.fft_size, "gps": {"latitude": self._lat, "longitude": self._lon, "altitude_m": self._alt}, "device_telemetry": self.telemetry.current(), "spectrum_agent": {"name": self.agent.name, "version": self.agent.version}}

    def latest_spectrum(self) -> dict:
        with self._lock:
            return self._latest or {"timestamp": None, "frequencies_hz": [], "power_db": [], "noise_floor_db": None, "center_frequency_hz": self.config.center_frequency, "sample_rate_hz": self.config.sample_rate, "source_type": self.source_type.value, "provenance": source_provenance(self.source), "detections": []}

    def waterfall(self) -> dict:
        with self._lock:
            source_status = self.source.status() if hasattr(self.source, "status") else {}
            return {"frames": list(self._waterfall), "frame_count": len(self._waterfall), "fft_size": self.config.fft_size, "sample_rate_hz": source_status.get("sample_rate_hz", self.config.sample_rate), "center_frequency_hz": source_status.get("center_frequency_hz", self.config.center_frequency), "source_type": self.source_type.value, "provenance": source_provenance(self.source)}

    def observations(self, limit: int = 250) -> list[dict]: return self.store.recent(limit)
