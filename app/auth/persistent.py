"""SQLite-backed authentication service."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from .models import Session, User
from .password import hash_password, verify_password
from .tokens import generate_access_token, generate_refresh_token, hash_token
from app.database.repositories import AuditRepository, UserRepository
from app.database.sqlite import Database

ACCESS_TOKEN_TTL = timedelta(minutes=15)
REFRESH_TOKEN_TTL = timedelta(days=30)


class PersistentAuthService:
    def __init__(self, db: Database):
        self.users = UserRepository(db)
        self.audit = AuditRepository(db)
        self.db = db

    def register(self, username: str, password: str, role: str = "viewer") -> User:
        username = username.strip().lower()
        if not username or len(password) < 12:
            raise ValueError("Username required and password must be at least 12 characters")
        if role not in {"viewer", "analyst", "operator", "admin", "owner"}:
            raise ValueError("Invalid role")
        if self.users.by_username(username):
            raise ValueError("User already exists")
        user = User(str(uuid.uuid4()), username, hash_password(password), role, True, datetime.utcnow())
        self.users.create(user)
        self.audit.record("user.register", user.id, "user", user.id)
        return user

    def login(self, username: str, password: str) -> tuple[str, str]:
        user = self.users.by_username(username.strip().lower())
        if user is None or not user.active or not verify_password(password, user.password_hash):
            self.audit.record("auth.login_failed", resource="user")
            raise ValueError("Invalid credentials")
        now = datetime.utcnow()
        access = generate_access_token()
        refresh = generate_refresh_token()
        session = Session(str(uuid.uuid4()), user.id, hash_token(refresh), now, now + REFRESH_TOKEN_TTL)
        self.db.execute("INSERT INTO sessions VALUES (?,?,?,?,?,?)", (session.id, session.user_id, session.refresh_token_hash, now.isoformat(), session.expires_at.isoformat(), None))
        self.db.execute("INSERT INTO access_tokens VALUES (?,?,?)", (hash_token(access), user.id, (now + ACCESS_TOKEN_TTL).isoformat()))
        self.audit.record("auth.login", user.id, "session", session.id)
        return access, refresh

    def authenticate(self, access_token: str) -> User | None:
        row = self.db.fetchone("SELECT user_id, expires_at FROM access_tokens WHERE token_hash=?", (hash_token(access_token),))
        if not row:
            return None
        if datetime.utcnow() >= datetime.fromisoformat(row["expires_at"]):
            self.db.execute("DELETE FROM access_tokens WHERE token_hash=?", (hash_token(access_token),))
            return None
        return self.users.by_id(row["user_id"])

    def logout(self, access_token: str) -> None:
        user = self.authenticate(access_token)
        self.db.execute("DELETE FROM access_tokens WHERE token_hash=?", (hash_token(access_token),))
        if user:
            self.audit.record("auth.logout", user.id, "session")
