"""Boundary for future authorized protocol decoders.

This module deliberately does not implement decryption, key recovery, or
protected-traffic interception. A concrete decoder may only be registered for
a supported protocol and invoked after the caller establishes authorization
and supplies legitimate key material through its own controlled interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class AuthorizedDecoder(Protocol):
    protocol: str

    def decode(self, payload: bytes, *, key_material: bytes) -> bytes:
        """Decode content using legitimately supplied key material."""
        ...


@dataclass(frozen=True)
class DecoderAuthorization:
    operator: str
    protocol: str
    authorized: bool
    audit_reference: str


class DecoderRegistry:
    """Registry that keeps unsupported protected decoding fail-closed."""

    def __init__(self) -> None:
        self._decoders: dict[str, AuthorizedDecoder] = {}

    def register(self, decoder: AuthorizedDecoder) -> None:
        protocol = str(decoder.protocol).strip().lower()
        if not protocol:
            raise ValueError("decoder protocol is required")
        self._decoders[protocol] = decoder

    def decode(self, protocol: str, payload: bytes, *, key_material: bytes, authorization: DecoderAuthorization) -> bytes:
        if not authorization.authorized:
            raise PermissionError("authorized decoding is required")
        normalized = str(protocol).strip().lower()
        if normalized != authorization.protocol.strip().lower():
            raise PermissionError("authorization protocol does not match decoder protocol")
        decoder = self._decoders.get(normalized)
        if decoder is None:
            raise NotImplementedError("no authorized decoder is installed for this protocol")
        if not key_material:
            raise ValueError("legitimate key material is required")
        return decoder.decode(payload, key_material=key_material)
