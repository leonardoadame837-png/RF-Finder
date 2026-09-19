"""Receive-only network SDR source for the rtl_tcp protocol.

The rtl_tcp server exposes an RTL2832-compatible receiver as an I/Q stream over
TCP. RF Finder consumes the unsigned 8-bit interleaved I/Q payload and converts
it to normalized complex samples before passing them to the existing DSP stack.
"""

from __future__ import annotations

import socket
import struct
from datetime import datetime, timezone

import numpy as np


class NetworkSDRUnavailableError(RuntimeError):
    """Raised when a network SDR backend cannot be reached or used."""


class RTLTCPSource:
    """Receive-only rtl_tcp source producing normalized complex I/Q frames."""

    def __init__(
        self,
        config,
        host: str = "127.0.0.1",
        port: int = 1234,
        timeout_s: float = 5.0,
    ):
        self.config = config
        self.host = host
        self.port = int(port)
        self.timeout_s = float(timeout_s)
        self.frame_index = 0
        self.running = False
        self._socket: socket.socket | None = None
        self._server_info: dict = {}
        self._last_timestamp: str | None = None
        self._center_frequency_hz = float(config.center_frequency)
        self._sample_rate_hz = float(config.sample_rate)

    def start(self) -> None:
        if self.running:
            return
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout_s)
        try:
            sock.connect((self.host, self.port))
            header = self._recv_exact(sock, 12)
            if header[:4] != b"RTL0":
                raise NetworkSDRUnavailableError("rtl_tcp server returned an invalid header")
            tuner_type, tuner_gain_count = struct.unpack("!II", header[4:12])
            self._server_info = {
                "tuner_type": tuner_type,
                "tuner_gain_count": tuner_gain_count,
            }
            self._set_frequency(sock, self.config.center_frequency)
            self._set_sample_rate(sock, self.config.sample_rate)
            self._set_gain(sock, self.config.sdr_gain)
        except (OSError, ValueError, struct.error, NetworkSDRUnavailableError) as exc:
            try:
                sock.close()
            except OSError:
                pass
            if isinstance(exc, NetworkSDRUnavailableError):
                raise
            raise NetworkSDRUnavailableError(
                f"Unable to connect to rtl_tcp at {self.host}:{self.port}: {exc}"
            ) from exc
        self._socket = sock
        self._center_frequency_hz = float(self.config.center_frequency)
        self._sample_rate_hz = float(self.config.sample_rate)
        self.frame_index = 0
        self.running = True

    def stop(self) -> None:
        self.running = False
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
        self._socket = None
        self.frame_index = 0
        self._last_timestamp = None

    @staticmethod
    def _recv_exact(sock: socket.socket, size: int) -> bytes:
        chunks = bytearray()
        while len(chunks) < size:
            chunk = sock.recv(size - len(chunks))
            if not chunk:
                raise NetworkSDRUnavailableError("rtl_tcp connection closed while reading I/Q data")
            chunks.extend(chunk)
        return bytes(chunks)

    @staticmethod
    def _command(cmd: int, value: int) -> bytes:
        return struct.pack("!BI", cmd, int(value) & 0xFFFFFFFF)

    def _send_command(self, cmd: int, value: int) -> None:
        if self._socket is None:
            raise RuntimeError("Network SDR socket is not connected")
        self._socket.sendall(self._command(cmd, value))

    def _set_frequency(self, sock: socket.socket, frequency_hz: int) -> None:
        sock.sendall(self._command(0x01, frequency_hz))
        self._center_frequency_hz = float(frequency_hz)

    def _set_sample_rate(self, sock: socket.socket, sample_rate_hz: int) -> None:
        sock.sendall(self._command(0x02, sample_rate_hz))
        self._sample_rate_hz = float(sample_rate_hz)

    def _set_gain(self, sock: socket.socket, gain: str | float) -> None:
        # rtl_tcp command 0x03 selects gain mode; 0 enables automatic gain.
        if str(gain).lower() == "auto":
            sock.sendall(self._command(0x03, 0))
            return
        # rtl_tcp expects tenths of a dB for manual gain (e.g. 40.0 dB -> 400).
        sock.sendall(self._command(0x03, 1))
        sock.sendall(self._command(0x04, round(float(gain) * 10)))

    def generate_frame(self) -> np.ndarray:
        if not self.running or self._socket is None:
            raise RuntimeError("Network SDR source is not running")
        raw = self._recv_exact(self._socket, self.config.fft_size * 2)
        samples = np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
        iq = (samples[0::2] - 127.5) / 127.5 + 1j * (samples[1::2] - 127.5) / 127.5
        self.frame_index += 1
        self._last_timestamp = datetime.now(timezone.utc).isoformat()
        return iq.astype(np.complex128)

    def set_frequency(self, frequency_hz: int) -> None:
        self._send_command(0x01, frequency_hz)
        self._center_frequency_hz = float(frequency_hz)

    def set_sample_rate(self, sample_rate_hz: int) -> None:
        self._send_command(0x02, sample_rate_hz)
        self._sample_rate_hz = float(sample_rate_hz)

    def status(self) -> dict:
        return {
            "active": self.running,
            "source": "network_sdr",
            "backend": "rtl_tcp",
            "host": self.host,
            "port": self.port,
            "sample_rate_hz": self._sample_rate_hz,
            "center_frequency_hz": self._center_frequency_hz,
            "gain": self.config.sdr_gain,
            "frame_index": self.frame_index,
            "last_timestamp": self._last_timestamp,
            "server_info": dict(self._server_info),
        }
