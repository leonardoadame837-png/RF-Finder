"""Authenticated Spectrum Analyzer HTTP service.

Serves the browser analyzer and exposes the same RFService/DSP pipeline;
it does not implement a second FFT or detector.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np

from app.api_auth import APIAuth
from app.auth import AuthManager
from app.audio_api import build_audio_wav
from app.field_service import RFService

MAX_IMPORT_BYTES = 8 * 1024 * 1024


def _decode_iq(payload: dict, fft_size: int) -> tuple[np.ndarray, dict]:
    samples = payload.get("samples")
    if not isinstance(samples, list) or len(samples) != fft_size:
        raise ValueError(f"samples must contain exactly {fft_size} complex samples")
    values = []
    for item in samples:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            real, imag = item
        elif isinstance(item, dict):
            real, imag = item.get("real"), item.get("imag")
        else:
            raise ValueError("each sample must be [I,Q] or {real,imag}")
        real, imag = float(real), float(imag)
        if not np.isfinite(real) or not np.isfinite(imag):
            raise ValueError("samples must contain finite values")
        values.append(real + 1j * imag)
    metadata = {"center_frequency_hz": payload.get("center_frequency_hz"), "sample_rate_hz": payload.get("sample_rate_hz"), "timestamp": payload.get("timestamp"), "sample_format": payload.get("sample_format", "complex64"), "source_type": payload.get("source_type", "IMPORTED_MEASUREMENT")}
    metadata = {k: v for k, v in metadata.items() if v is not None}
    return np.asarray(values, dtype=np.complex128), metadata


def create_server(service: RFService, host: str = "127.0.0.1", port: int = 8090, auth: APIAuth | None = None):
    api_auth = auth or APIAuth(AuthManager())
    ui_path = Path(__file__).resolve().parent.parent / "docs" / "spectrum.html"

    class Handler(BaseHTTPRequestHandler):
        def _send(self, payload, status=200, content_type="application/json"):
            body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            self.send_response(status); self.send_header("Content-Type", content_type); self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

        def _json_body(self):
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_IMPORT_BYTES: raise ValueError("request body is empty or too large")
            return json.loads(self.rfile.read(length))

        def _require(self, permission=None): return api_auth.require(self.headers.get("Authorization"), permission)

        def do_GET(self):
            path = urlparse(self.path).path
            if path in ("/", "/spectrum"):
                try: self._send(ui_path.read_bytes(), content_type="text/html; charset=utf-8")
                except OSError: self._send({"error": "Spectrum Analyzer UI is unavailable"}, 500)
                return
            try:
                if path == "/api/auth/me":
                    p = self._require(None); return self._send({"username": p.user.username, "role": p.user.role})
                if path == "/api/status": self._require("rf.read"); return self._send(service.status())
                if path == "/api/spectrum": self._require("rf.read"); return self._send(service.latest_spectrum())
                if path == "/api/waterfall": self._require("rf.read"); return self._send(service.waterfall())
                if path == "/api/observations": self._require("rf.read"); return self._send(service.observations())
                if path == "/api/audio":
                    self._require("rf.read")
                    query = parse_qs(urlparse(self.path).query)
                    mode = str(query.get("mode", ["fm"])[0]).lower()
                    bandwidth = query.get("bandwidth_hz", [None])[0]
                    bandwidth_hz = None if bandwidth in (None, "") else float(bandwidth)
                    audio = build_audio_wav(service, mode, bandwidth_hz)
                    return self._send(audio, content_type="audio/wav")
                return self._send({"error": "not found"}, 404)
            except PermissionError as exc:
                return self._send({"error": str(exc)}, 401 if str(exc) == "Authentication required" else 403)
            except (ValueError, TypeError, OSError) as exc:
                return self._send({"error": str(exc)}, 400)

        def do_POST(self):
            path = urlparse(self.path).path
            try:
                if path == "/api/auth/login":
                    data = self._json_body(); session = api_auth.login(str(data.get("username", "")), str(data.get("password", "")))
                    return self._send({"token": session.token, "expires_at": session.expires_at, "username": session.user.username, "role": session.user.role})
                if path == "/api/auth/logout":
                    self._require(None); api_auth.logout(self.headers.get("Authorization")); return self._send({"ok": True})
                if path == "/api/start":
                    self._require("rf.scan"); service.start(); return self._send(service.status())
                if path == "/api/stop":
                    self._require("rf.scan"); service.stop(); return self._send(service.status())
                if path == "/api/import":
                    self._require("rf.scan"); data = self._json_body(); iq, metadata = _decode_iq(data, service.config.fft_size); return self._send(service.ingest_imported(iq, metadata))
                return self._send({"error": "not found"}, 404)
            except PermissionError as exc:
                return self._send({"error": str(exc)}, 401 if str(exc) == "Authentication required" else 403)
            except (ValueError, TypeError, OSError, json.JSONDecodeError) as exc:
                return self._send({"error": str(exc)}, 400)

        def log_message(self, format, *args): return

    return ThreadingHTTPServer((host, port), Handler)


if __name__ == "__main__":
    import os
    service = RFService(); service.start(); host = os.getenv("RF_FINDER_SPECTRUM_HOST", "127.0.0.1"); port = int(os.getenv("RF_FINDER_SPECTRUM_PORT", "8090")); server = create_server(service, host, port); print(f"RF Finder Spectrum Analyzer: http://{host}:{port}/spectrum")
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: service.stop(); server.server_close()
