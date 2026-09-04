"""Continuous RF field service tying source, DSP, persistence and UI state together."""

from __future__ import annotations

import os
import threading
import time
from collections import deque
from datetime import datetime, timezone

from app.config import default_config
from app.dsp.analyzer import SpectrumAnalyzer
from app.dsp.detector import SignalDetector
from app.observation import RFObservation, classify_observation
from app.sources.simulator import SignalSimulator
from app.storage import ObservationStore


class RFService:
    """Continuous laptop-first RF monitoring service."""

    def __init__(self, config=default_config, source=None, scan_interval_s: float = 0.5):
        self.config = config
        self.source = source or SignalSimulator(config)
        self.analyzer = SpectrumAnalyzer(config)
        self.detector = SignalDetector(config)
        self.store = ObservationStore(config.database_path)
        self.scan_interval_s = max(0.05, float(scan_interval_s))
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.RLock()
        self._running = False
        self._frame_index = 0
        self._last_error: str | None = None
        self._latest = None
        self._waterfall = deque(maxlen=config.waterfall_history_frames)
        self._last_scan_at: str | None = None
        self._lat = self._env_float("RF_FINDER_LAT")
        self._lon = self._env_float("RF_FINDER_LON")
        self._alt = self._env_float("RF_FINDER_ALT_M")

    @staticmethod
    def _env_float(name):
        value = os.getenv(name)
        return float(value) if value not in (None, "") else None

    @property
    def source_name(self) -> str:
        return getattr(self.source, "status", lambda: {"source": "unknown"})().get("source", "unknown")

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self.source.start()
            self._stop.clear()
            self._running = True
            self._last_error = None
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
                    # A source may have advanced its own frame counter before
                    # a DSP/storage error. Preserve that progress in the API so
                    # operators can distinguish a live source from a stalled one.
                    source_frame = getattr(self.source, "frame_index", self._frame_index)
                    self._frame_index = max(self._frame_index, int(source_frame))
                    self._last_error = f"{type(exc).__name__}: {exc}"
            delay = self.scan_interval_s - (time.monotonic() - started)
            if delay > 0:
                self._stop.wait(delay)

    def scan_once(self) -> dict:
        iq = self.source.generate_frame()
        frequencies, power, noise_floor = self.analyzer.analyze(iq)
        frame_index = getattr(self.source, "frame_index", self._frame_index + 1)
        detections = self.detector.detect(frequencies, power, noise_floor, frame_index)

        spectrum = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "frequencies_hz": [float(x) for x in frequencies.tolist()],
            "power_db": [float(x) for x in power.tolist()],
            "noise_floor_db": float(noise_floor),
            "center_frequency_hz": float(self.config.center_frequency),
            "sample_rate_hz": float(self.config.sample_rate),
        }
        with self._lock:
            self._frame_index = int(frame_index)
            self._latest = spectrum
            self._waterfall.append(spectrum["power_db"])
            self._last_scan_at = spectrum["timestamp"]

        for detection in detections:
            observation = RFObservation(
                timestamp=spectrum["timestamp"],
                frequency_hz=detection.center_frequency_hz,
                peak_power_db=detection.peak_power_db,
                noise_floor_db=detection.noise_floor_db,
                snr_db=detection.snr_db,
                bandwidth_hz=detection.bandwidth_hz,
                latitude=self._lat,
                longitude=self._lon,
                altitude_m=self._alt,
                source=self.source_name,
                signal_class="unknown",
                confidence=0.0,
                evidence="simulated_signal" if self.source_name == "simulator" else "rf_measurement",
                simulated=self.source_name == "simulator",
            )
            self.store.add(classify_observation(observation))

        return {
            "frame_index": frame_index,
            "detections": len(detections),
            "noise_floor_db": float(noise_floor),
        }

    def status(self) -> dict:
        with self._lock:
            source_status = self.source.status() if hasattr(self.source, "status") else {}
            return {
                "running": self._running,
                "source": self.source_name,
                "source_status": source_status,
                "frame_index": self._frame_index,
                "last_scan_at": self._last_scan_at,
                "last_error": self._last_error,
                "center_frequency_hz": self.config.center_frequency,
                "sample_rate_hz": self.config.sample_rate,
                "fft_size": self.config.fft_size,
                "gps": {"latitude": self._lat, "longitude": self._lon, "altitude_m": self._alt},
            }

    def latest_spectrum(self) -> dict:
        with self._lock:
            return self._latest or {
                "timestamp": None,
                "frequencies_hz": [],
                "power_db": [],
                "noise_floor_db": None,
                "center_frequency_hz": self.config.center_frequency,
                "sample_rate_hz": self.config.sample_rate,
            }

    def waterfall(self) -> dict:
        with self._lock:
            return {
                "frames": list(self._waterfall),
                "frame_count": len(self._waterfall),
                "fft_size": self.config.fft_size,
                "sample_rate_hz": self.config.sample_rate,
                "center_frequency_hz": self.config.center_frequency,
            }

    def observations(self, limit: int = 250) -> list[dict]:
        return self.store.recent(limit)
