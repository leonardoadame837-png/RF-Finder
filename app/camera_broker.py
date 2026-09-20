"""Backend RTSP camera broker for RF Finder.

The broker keeps camera credentials server-side and uses ffmpeg to turn RTSP into
browser-consumable HLS. It is deliberately receive-only: no camera control APIs
are exposed here.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone


class CameraBroker:
    def __init__(self, root: str | None = None, event_callback=None):
        self.root = Path(root or (Path(tempfile.gettempdir()) / "rf-finder-camera-streams"))
        self.root.mkdir(parents=True, exist_ok=True)
        self.event_callback = event_callback
        self._lock = threading.RLock()
        self._processes: dict[int, subprocess.Popen] = {}

    @staticmethod
    def _password(camera_id: int) -> str:
        return os.getenv(f"RF_FINDER_CAMERA_{int(camera_id)}_PASSWORD", "")

    @staticmethod
    def _rtsp_url(camera: dict) -> str:
        override = os.getenv(f"RF_FINDER_CAMERA_{int(camera['id'])}_RTSP_URL", "").strip()
        if override:
            return override
        path = str(camera.get("stream_path") or "/").strip()
        if not path.startswith("/"):
            path = "/" + path
        username = str(camera.get("username") or "")
        password = CameraBroker._password(camera["id"])
        auth = ""
        if username:
            auth = urllib.parse.quote(username, safe="") + ":"
            auth += urllib.parse.quote(password, safe="") + "@"
        return f"{camera['protocol']}://{auth}{camera['host']}:{int(camera['port'])}{path}"

    def start(self, camera: dict) -> dict:
        camera_id = int(camera["id"])
        with self._lock:
            existing = self._processes.get(camera_id)
            if existing and existing.poll() is None:
                return self.status(camera)
            if camera.get("protocol") not in {"rtsp", "rtsps"}:
                raise ValueError("The broker currently requires an RTSP/RTSPS stream URL")
            if camera.get("username") and not self._password(camera_id):
                raise ValueError("Camera password is not configured on the backend")
            if not shutil.which("ffmpeg"):
                raise RuntimeError("ffmpeg is required for live camera playback")
            out = self.root / str(camera_id)
            out.mkdir(parents=True, exist_ok=True)
            for item in out.glob("*"):
                if item.is_file():
                    item.unlink()
            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "warning",
                "-rtsp_transport", "tcp", "-i", self._rtsp_url(camera),
                "-c:v", "copy",
            ]
            if camera.get("audio_enabled"):
                cmd += ["-c:a", "aac", "-ar", "48000"]
            else:
                cmd += ["-an"]
            cmd += [
                "-f", "hls", "-hls_time", "1", "-hls_list_size", "3",
                "-hls_flags", "delete_segments+append_list",
                str(out / "index.m3u8"),
            ]
            process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            self._processes[camera_id] = process
            self._emit(camera, "CAMERA_STREAM_STARTED", {"state": "STARTING"})
            return self.status(camera)

    def stop(self, camera_id: int) -> dict:
        camera_id = int(camera_id)
        with self._lock:
            process = self._processes.pop(camera_id, None)
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
            return {"camera_id": camera_id, "state": "STOPPED"}

    def status(self, camera: dict) -> dict:
        camera_id = int(camera["id"])
        with self._lock:
            process = self._processes.get(camera_id)
            if not process:
                return {"camera_id": camera_id, "state": "STOPPED"}
            code = process.poll()
            if code is not None:
                return {"camera_id": camera_id, "state": "FAILED", "exit_code": code}
            playlist = self.root / str(camera_id) / "index.m3u8"
            return {
                "camera_id": camera_id,
                "state": "LIVE" if playlist.exists() else "STARTING",
                "hls_path": f"/api/cameras/{camera_id}/stream/index.m3u8",
            }

    def stream_file(self, camera_id: int, relative_path: str) -> Path | None:
        base = (self.root / str(int(camera_id))).resolve()
        target = (base / relative_path).resolve()
        try:
            target.relative_to(base)
        except ValueError:
            return None
        return target if target.is_file() else None

    def _emit(self, camera: dict, event_type: str, payload: dict):
        if not self.event_callback:
            return
        self.event_callback({
            "event_id": f"camera-{camera['id']}-{datetime.now(timezone.utc).timestamp():.6f}",
            "event_type": event_type,
            "source_id": f"camera-{camera['id']}",
            "source_type": "CAMERA_VIDEO",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        })

    def stop_all(self):
        with self._lock:
            ids = list(self._processes)
        for camera_id in ids:
            self.stop(camera_id)
