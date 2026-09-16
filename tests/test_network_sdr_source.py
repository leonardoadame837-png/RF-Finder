import struct

import numpy as np

from app.config import Config
from app.sources.base import source_provenance
from app.sources.network import RTLTCPSource
from app.sources.types import SourceType, normalize_source_type


class FakeSocket:
    def __init__(self, payload: bytes):
        self.payload = bytearray(payload)
        self.sent = []
        self.timeout = None

    def recv(self, size: int) -> bytes:
        chunk = bytes(self.payload[:size])
        del self.payload[:size]
        return chunk

    def sendall(self, data: bytes) -> None:
        self.sent.append(data)

    def settimeout(self, timeout: float) -> None:
        self.timeout = timeout

    def close(self) -> None:
        pass


def test_rtl_tcp_command_encoding_is_network_order():
    assert RTLTCPSource._command(0x01, 100_000_000) == struct.pack("!BI", 0x01, 100_000_000)


def test_rtl_tcp_frame_decodes_unsigned_interleaved_iq():
    config = Config(fft_size=4)
    source = RTLTCPSource(config)
    source._socket = FakeSocket(bytes([0, 255, 127, 128, 255, 0, 128, 127]))
    source.running = True

    frame = source.generate_frame()

    assert frame.shape == (4,)
    assert frame.dtype == np.complex128
    assert np.isclose(frame[0].real, -1.0)
    assert np.isclose(frame[0].imag, 1.0)
    assert source.frame_index == 1


def test_network_sdr_is_live_verified_provenance():
    config = Config()
    source = RTLTCPSource(config)
    provenance = source_provenance(source)

    assert normalize_source_type("network_sdr") is SourceType.LIVE_MEASUREMENT
    assert provenance["source_type"] == SourceType.LIVE_MEASUREMENT.value
    assert provenance["verified_rf"] is True
    assert provenance["capture_kind"] == "hardware_iq"
