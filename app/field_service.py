"""Continuous RF field service tying source, DSP, persistence and UI state together."""

from __future__ import annotations

import os
import platform
import threading
import time
from collections import deque
from datetime import datetime, timezone

from app.ai_spectrum_agent import LocalSpectrumAnalyst, build_agent_context
from app.config import default_config
from app.device_telemetry import TelemetryStore
from app.dsp.analyzer import SpectrumAnalyzer
from app.dsp.detector import Detection, SignalDetector
from app.observation import RFObservation, classify_observation
from app.source_types import SourceType, normalize_source_type
from app.sources.base import source_provenance
from app.sources.simulator import SignalSimulator
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
        self._stop = threading.Event()
        self._lock = threading.RLock()
        self._running = False
        self._frame_index = 0
        self._last_error: str | None = None
        self._latest = None
        self._latest_detections: list[Detection] = []
        self._waterfall = deque(maxlen=config.waterfall_history_frames)
        self._last_scan_at: str | None = None
        self._lat = self._env_float("RF_FINDER_LAT")
        self._lon = self._env_float("RF_FINDER_LON")
        self._alt = self._env_float("RF_FINDER_ALT_M")

    @staticmethod
    def _build_source(config):
        mode = str(config.source).lower()
        if mode == "simulator":
            return SignalSimulator(config)
        if mode == "sdr":
            from app.sources.sdr import RTLSDRSource
            return RTLSDRSource(config, device_index=config.sdr_device_index, gain=config.sdr_gain)
        raise ValueError(f"Unsupported RF source: {config.source!r}")

    @staticmethod
    def _env_float(name):
        value = os.getenv(name)
        return float(value) if value not in (None, "") else None

    @property
    def source_name(self) -> str:
        return source_provenance(self.source)["source_type"]

    @property
    def source_type(self) -> SourceType:
        return normalize_source_type(source_provenance(self.source)["source_type"])

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self.source.start()
            self._stop.clear()
            self._running = True
            self._last_error = None
        try:
            self.scan_once()
        except Exception as exc:
            with self._lock:
                source_frame = getattr(self.source, "frame_index", self._frame_index)
                self._frame_index = max(self._frame_index, int(source_frame))
                self._last_error = f"{type(exc).__name__}: {exc}"
        with self._lock:
            if not self._running:
                return
            self._thread = threading.Thread(target=self._run, name="rf-finder-scan", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._stop.set()
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=max(1.0, self.scan_interval_s * 3))
        try:
            self.source.stop()
        except Exception:
            pass

    def _run(self) -> None:
        while not self._stop.is_set():
            started = time.monotonic()
            try:
                self.scan_once()
            except Exception as exc:
                with self._lock:
                    source_frame = getattr(self.source, "frame_index", self._frame_index)
                    self._frame_index = max(self._frame_index, int(source_frame))
                    self._last_error = f"{type(exc).__name__}: {exc}"
            delay = self.scan_interval_s - (time.monotonic() - started)
            if delay > 0:
                self._stop.wait(delay)

    def _process_frame(self, iq, source_type: SourceType, timestamp: str) -> dict:
        frequencies, power, noise_floor = self.analyzer.analyze(iq)
        frame_index = getattr(self.source, "frame_index", self._frame_index + 1)
        detections = self.detector.detect(
            frequencies, power, noise_floor, frame_index,
            source_type=source_type, timestamp=timestamp,
        )
        spectrum = self.analyzer.analyze_frame(iq, source_type, timestamp)
        spectrum["provenance"] = {
            "source_type": source_type.value,
            "verified_rf": source_type.is_measurement,
            "simulated": source_type is SourceType.SIMULATED,
        }
        spectrum["detections"] = [d.to_dict() for d in detections]
        with self._lock:
            self._frame_index = int(frame_index)
            self._latest = spectrum
            self._latest_detections = detections
            self._waterfall.append(spectrum["power_dbfs"])
            self._last_scan_at = timestamp
        return {"frame_index": frame_index, "detections": len(detections), "noise_floor_dbfs": float(noise_floor)}

    def scan_once(self) -> dict:
        iq = self.source.generate_frame()
        timestamp = datetime.now(timezone.utc).isoformat()
        result = self._process_frame(iq, self.source_type, timestamp)
        for detection in self._latest_detections:
            simulated = detection.source_type is SourceType.SIMULATED
            observation = RFObservation(
                timestamp=detection.timestamp,
                frequency_hz=detection.frequency_hz,
                peak_power_db=detection.power_dbfs,
                noise_floor_db=detection.noise_floor_dbfs,
                snr_db=detection.snr_db,
                bandwidth_hz=detection.bandwidth_hz,
                latitude=self._lat,
                longitude=self._lon,
                altitude_m=self._alt,
                source=detection.source_type.value,
                source_type=detection.source_type.value,
                signal_class="unknown",
                confidence=detection.confidence,
                evidence="simulated_signal" if simulated else "rf_measurement",
                simulated=simulated,
            )
            self.store.add(classify_observation(observation))
        return result

    def import_measurement(self, iq, metadata: dict | None = None) -> dict:
        """Analyze imported samples without claiming they originated from hardware."""
        metadata = metadata or {}
        source = normalize_source_type(metadata.get("source_type", SourceType.IMPORTED_MEASUREMENT.value))
        if source is SourceType.SIMULATED:
            # Explicitly supplied simulation remains simulation; it can never be upgraded.
            source = SourceType.SIMULATED
        timestamp = str(metadata.get("timestamp") or datetime.now(timezone.utc).isoformat())
        result = self._process_frame(iq, source, timestamp)
        return {"spectrum": self.latest_spectrum(), **result}

    def update_telemetry(self, payload: dict) -> dict:
        return self.telemetry.update(payload)

    def spectrum_agent_analysis(self) -> dict:
        spectrum = self.latest_spectrum()
        observations = self.observations(limit=30)
        context = build_agent_context(spectrum, observations)
        return self.agent.analyze(context)

    def status(self) -> dict:
        with self._lock:
            source_status = self.source.status() if hasattr(self.source, "status") else {}
            provenance = source_provenance(self.source)
            return {
                "running": self._running,
                "platform": platform.system().lower(),
                "client_architecture": "browser + local RF service",
                "source": self.source_name,
                "source_type": provenance["source_type"],
                "source_status": source_status,
                "provenance": provenance,
                "frame_index": self._frame_index,
                "last_scan_at": self._last_scan_at,
                "last_error": self._last_error,
                "center_frequency_hz": self.config.center_frequency,
                "sample_rate_hz": self.config.sample_rate,
                "fft_size": self.config.fft_size,
                "gps": {"latitude": self._lat, "longitude": self._lon, "altitude_m": self._alt},
                "device_telemetry": self.telemetry.current(),
                "spectrum_agent": {"name": self.agent.name, "version": self.agent.version},
            }

    def latest_spectrum(self) -> dict:
        with self._lock:
            return self._latest or {
                "timestamp": None,
                "frequencies_hz": [],
                "power_dbfs": [],
                "noise_floor_dbfs": None,
                "center_frequency_hz": self.config.center_frequency,
                "sample_rate_hz": self.config.sample_rate,
                "source_type": self.source_type.value,
                "provenance": source_provenance(self.source),
                "detections": [],
            }

    def waterfall(self) -> dict:
        with self._lock:
            return {
                "frames": list(self._waterfall),
                "frame_count": len(self._waterfall),
                "fft_size": self.config.fft_size,
                "sample_rate_hz": self.config.sample_rate,
                "center_frequency_hz": self.config.center_frequency,
                "source_type": self.source_type.value,
                "provenance": source_provenance(self.source),
            }

    def detections(self, limit: int = 250) -> list[dict]:
        with self._lock:
            return [d.to_dict() for d in self._latest_detections[:max(1, min(1000, limit))]]

    def observations(self, limit: int = 250) -> list[dict]:
        return self.store.recent(limit)
