"""In-memory authentication service for the local prototype.

The service intentionally keeps persistence separate. A later database
repository can implement the same operations without changing callers.
"""

from datetime import datetime, timedelta
import secrets
import uuid

from .models import Session, User
from .password import hash_password, verify_password
from .tokens import generate_access_token, generate_refresh_token, hash_token

ACCESS_TOKEN_TTL = timedelta(minutes=15)
REFRESH_TOKEN_TTL = timedelta(days=30)


class AuthService:
    def __init__(self) -> None:
        self._users: dict[str, User] = {}
        self._sessions: dict[str, Session] = {}
        self._access_tokens: dict[str, tuple[str, datetime]] = {}

    def register(self, username: str, password: str, role: str = "viewer") -> User:
        normalized = username.strip().lower()
        if not normalized or len(password) < 12:
            raise ValueError("Username is required and password must be at least 12 characters")
        if any(u.username == normalized for u in self._users.values()):
            raise ValueError("User already exists")
        if role not in {"viewer", "analyst", "operator", "admin", "owner"}:
            raise ValueError("Invalid role")
        user = User(str(uuid.uuid4()), normalized, hash_password(password), role, True, datetime.utcnow())
        self._users[user.id] = user
        return user

    def login(self, username: str, password: str) -> tuple[str, str]:
        normalized = username.strip().lower()
        user = next((u for u in self._users.values() if u.username == normalized), None)
        if user is None or not user.active or not verify_password(password, user.password_hash):
            raise ValueError("Invalid credentials")

        now = datetime.utcnow()
        access = generate_access_token()
        refresh = generate_refresh_token()
        session = Session(str(uuid.uuid4()), user.id, hash_token(refresh), now, now + REFRESH_TOKEN_TTL)
        self._sessions[session.id] = session
        self._access_tokens[hash_token(access)] = (user.id, now + ACCESS_TOKEN_TTL)
        return access, refresh

    def authenticate(self, access_token: str) -> User | None:
        record = self._access_tokens.get(hash_token(access_token))
        if record is None:
            return None
        user_id, expires_at = record
        if datetime.utcnow() >= expires_at:
            self._access_tokens.pop(hash_token(access_token), None)
            return None
        return self._users.get(user_id)

    def logout(self, access_token: str) -> None:
        self._access_tokens.pop(hash_token(access_token), None)
