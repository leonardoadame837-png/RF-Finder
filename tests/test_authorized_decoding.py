import pytest

from app.authorized_decoding import DecoderAuthorization, DecoderRegistry


class EchoDecoder:
    protocol = "test-protocol"

    def decode(self, payload: bytes, *, key_material: bytes) -> bytes:
        return payload + key_material


def test_unauthorized_decode_is_rejected():
    registry = DecoderRegistry()
    registry.register(EchoDecoder())
    auth = DecoderAuthorization("tester", "test-protocol", False, "audit-1")
    with pytest.raises(PermissionError):
        registry.decode("test-protocol", b"payload", key_material=b"key", authorization=auth)


def test_unsupported_protocol_fails_closed():
    registry = DecoderRegistry()
    auth = DecoderAuthorization("tester", "unknown", True, "audit-2")
    with pytest.raises(NotImplementedError):
        registry.decode("unknown", b"payload", key_material=b"key", authorization=auth)


def test_registered_decoder_requires_key_material():
    registry = DecoderRegistry()
    registry.register(EchoDecoder())
    auth = DecoderAuthorization("tester", "test-protocol", True, "audit-3")
    with pytest.raises(ValueError):
        registry.decode("test-protocol", b"payload", key_material=b"", authorization=auth)
