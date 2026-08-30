"""Opaque access and refresh token helpers.

Tokens are random values; only hashes should be persisted. This deliberately
avoids putting user data or secrets inside client-visible tokens.
"""

import hashlib
import secrets

ACCESS_TOKEN_BYTES = 32
REFRESH_TOKEN_BYTES = 48


def generate_access_token() -> str:
    return secrets.token_urlsafe(ACCESS_TOKEN_BYTES)


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(REFRESH_TOKEN_BYTES)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
