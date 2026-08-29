"""Authentication domain models."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class User:
    id: str
    username: str
    password_hash: str
    role: str = "viewer"
    active: bool = True
    created_at: Optional[datetime] = None


@dataclass(frozen=True)
class Session:
    id: str
    user_id: str
    refresh_token_hash: str
    created_at: datetime
    expires_at: datetime
    revoked_at: Optional[datetime] = None

    @property
    def active(self) -> bool:
        return self.revoked_at is None and datetime.utcnow() < self.expires_at
