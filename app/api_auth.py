"""Authentication and RBAC helpers for the RF Finder HTTP API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.auth import AuthError, AuthManager, Session, User


ROLE_PERMISSIONS = {
    "user": frozenset({"rf.read", "rf.scan", "investigation.read", "investigation.write"}),
    "admin": frozenset({"rf.read", "rf.scan", "investigation.read", "investigation.write", "admin.users"}),
}


@dataclass(frozen=True)
class APIPrincipal:
    user: User
    session: Session

    def can(self, permission: str) -> bool:
        return permission in ROLE_PERMISSIONS.get(self.user.role, frozenset())


class APIAuth:
    """Adapter that authenticates Bearer tokens and applies role permissions."""

    def __init__(self, auth: AuthManager | None = None):
        self.auth = auth or AuthManager()

    def login(self, username: str, password: str) -> Session:
        return self.auth.authenticate(username, password)

    def principal_from_header(self, authorization: str | None) -> APIPrincipal | None:
        if not authorization or not authorization.startswith("Bearer "):
            return None
        token = authorization[7:].strip()
        if not token:
            return None
        user = self.auth.validate_token(token)
        if user is None:
            return None
        session = self.auth._sessions.get(token)
        if session is None:
            return None
        return APIPrincipal(user=user, session=session)

    def require(self, authorization: str | None, permission: str | None = None) -> APIPrincipal:
        principal = self.principal_from_header(authorization)
        if principal is None:
            raise PermissionError("Authentication required")
        if permission and not principal.can(permission):
            raise PermissionError("Not authorized for this RF Finder operation")
        return principal

    def logout(self, authorization: str | None) -> bool:
        principal = self.principal_from_header(authorization)
        if principal is None:
            return False
        self.auth.logout(principal.session.token)
        return True
