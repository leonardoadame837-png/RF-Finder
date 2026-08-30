"""Local authentication for RF Finder.

Passwords are stored as salted PBKDF2-HMAC-SHA256 hashes. Session tokens are
random, in-memory values and are never persisted to disk.
"""

from __future__ import annotations

import base64
import getpass
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PBKDF2_ITERATIONS = 600_000
SALT_BYTES = 16
TOKEN_BYTES = 32
DEFAULT_SESSION_TTL_SECONDS = 3600


@dataclass(frozen=True)
class User:
    username: str
    role: str = "user"


@dataclass
class Session:
    user: User
    token: str
    expires_at: float


class AuthError(Exception):
    """Raised for authentication and account errors."""


class AuthManager:
    """Manage a single local RF Finder account and process-local sessions."""

    def __init__(self, users_path: str | Path = "data/auth/users.json", session_ttl: int = DEFAULT_SESSION_TTL_SECONDS):
        self.users_path = Path(users_path)
        self.session_ttl = session_ttl
        self._sessions: dict[str, Session] = {}

    def has_account(self) -> bool:
        return self.users_path.exists() and bool(self._load_users())

    def create_account(self, username: str, password: str, role: str = "user") -> User:
        username = username.strip()
        if not username or len(username) > 64:
            raise AuthError("Username must be between 1 and 64 characters.")
        if len(password) < 10:
            raise AuthError("Password must contain at least 10 characters.")
        if role not in {"user", "admin"}:
            raise AuthError("Invalid role.")

        users = self._load_users()
        if username in users:
            raise AuthError("Account already exists.")

        salt = secrets.token_bytes(SALT_BYTES)
        password_hash = _hash_password(password, salt)
        users[username] = {
            "role": role,
            "salt": base64.b64encode(salt).decode("ascii"),
            "password_hash": base64.b64encode(password_hash).decode("ascii"),
            "iterations": PBKDF2_ITERATIONS,
        }
        self._save_users(users)
        return User(username=username, role=role)

    def authenticate(self, username: str, password: str) -> Session:
        username = username.strip()
        record = self._load_users().get(username)
        if record is None:
            raise AuthError("Invalid username or password.")

        try:
            salt = base64.b64decode(record["salt"])
            expected = base64.b64decode(record["password_hash"])
            iterations = int(record.get("iterations", PBKDF2_ITERATIONS))
        except (KeyError, ValueError, TypeError):
            raise AuthError("Authentication data is invalid.") from None

        actual = _hash_password(password, salt, iterations)
        if not hmac.compare_digest(actual, expected):
            raise AuthError("Invalid username or password.")

        user = User(username=username, role=str(record.get("role", "user")))
        token = secrets.token_urlsafe(TOKEN_BYTES)
        session = Session(user=user, token=token, expires_at=time.time() + self.session_ttl)
        self._sessions[token] = session
        return session

    def validate_token(self, token: str) -> User | None:
        session = self._sessions.get(token)
        if session is None:
            return None
        if session.expires_at <= time.time():
            self._sessions.pop(token, None)
            return None
        return session.user

    def logout(self, token: str) -> None:
        self._sessions.pop(token, None)

    def _load_users(self) -> dict[str, dict[str, Any]]:
        if not self.users_path.exists():
            return {}
        try:
            data = json.loads(self.users_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AuthError("Unable to read authentication data.") from exc
        return data if isinstance(data, dict) else {}

    def _save_users(self, users: dict[str, dict[str, Any]]) -> None:
        self.users_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.users_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(users, indent=2), encoding="utf-8")
        temp_path.replace(self.users_path)


def _hash_password(password: str, salt: bytes, iterations: int = PBKDF2_ITERATIONS) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)


def first_run_setup(auth: AuthManager) -> None:
    """Interactively create the first local account."""
    print("No RF Finder account exists. Create the local administrator account.")
    while True:
        username = input("Username: ").strip()
        password = getpass.getpass("Password (10+ characters): ")
        confirmation = getpass.getpass("Confirm password: ")
        if password != confirmation:
            print("Passwords do not match. Try again.")
            continue
        try:
            auth.create_account(username, password, role="admin")
            print("Account created. Please sign in.")
            return
        except AuthError as exc:
            print(f"Account setup failed: {exc}")


def login_prompt(auth: AuthManager) -> Session:
    """Prompt until valid local credentials are supplied."""
    while True:
        username = input("Username: ").strip()
        password = getpass.getpass("Password: ")
        try:
            return auth.authenticate(username, password)
        except AuthError:
            print("Invalid username or password.")
