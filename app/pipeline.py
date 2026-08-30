"""RF capture pipeline: source -> DSP -> persistent measurements."""
from __future__ import annotations

import uuid
from datetime import datetime

from app.database.repositories import AuditRepository, MeasurementRepository
from app.dsp.analyzer import SpectrumAnalyzer
from app.dsp.detector import SignalDetector
from app.gps.location import GpsProvider


class RfCapturePipeline:
    def __init__(self, config, source, db, device_id=None, gps=None):
        self.config = config
        self.source = source
        self.db = db
        self.measurements = MeasurementRepository(db)
        self.audit = AuditRepository(db)
        self.analyzer = SpectrumAnalyzer(config)
        self.detector = SignalDetector(config)
        self.device_id = device_id
        self.gps = gps or GpsProvider()

    def run(self, frames: int | None = None, user_id: str | None = None) -> list[dict]:
        count = frames if frames is not None else self.config.num_frames
        location = self.gps.current_location()
        capture_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO captures VALUES (?,?,?,?,?,?,?,?)", (capture_id, self.device_id, datetime.utcnow().isoformat(), self.config.center_frequency, self.config.sample_rate, location.latitude, location.longitude, self.config.source))
        self.source.start()
        results = []
        try:
            for frame_index in range(count):
                iq = self.source.generate_frame()
                frequencies, spectrum, noise_floor = self.analyzer.analyze(iq)
                detections = self.detector.detect(frequencies, spectrum, noise_floor, frame_index)
                for detection in detections:
                    measurement_id = self.measurements.add(detection, capture_id)
                    results.append({"id": measurement_id, "capture_id": capture_id, "frequency_hz": detection.center_frequency_hz, "snr_db": detection.snr_db})
        finally:
            self.source.stop()
        self.audit.record("capture.completed", user_id, "capture", capture_id, metadata={"detections": len(results)})
        return results
