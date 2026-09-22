"""Authentication and RBAC helpers for the RF Finder HTTP API."""

from __future__ import annotations

from dataclasses import dataclass
from http.cookies import CookieError, SimpleCookie

from app.auth import AuthManager, Session, User


ROLE_PERMISSIONS = {
    "user": frozenset({
        "rf.read",
        "rf.scan",
        "investigation.read",
        "investigation.write",
        "telemetry.read",
        "telemetry.write",
    }),
    "admin": frozenset({
        "rf.read",
        "rf.scan",
        "investigation.read",
        "investigation.write",
        "telemetry.read",
        "telemetry.write",
        "admin.users",
    }),
}

SESSION_COOKIE = "rf_finder_session"


@dataclass(frozen=True)
class APIPrincipal:
    user: User
    session: Session

    def can(self, permission: str) -> bool:
        return permission in ROLE_PERMISSIONS.get(self.user.role, frozenset())


class APIAuth:
    """Authenticate Bearer tokens or the shared local RF Finder session cookie."""

    def __init__(self, auth: AuthManager | None = None):
        self.auth = auth or AuthManager()

    def login(self, username: str, password: str) -> Session:
        return self.auth.authenticate(username, password)

    def principal_from_header(self, authorization: str | None) -> APIPrincipal | None:
        if not authorization or not authorization.startswith("Bearer "):
            return None
        token = authorization[7:].strip()
        return self._principal_from_token(token)

    def principal_from_cookie(self, cookie_header: str | None) -> APIPrincipal | None:
        if not cookie_header:
            return None
        cookie = SimpleCookie()
        try:
            cookie.load(cookie_header)
        except (CookieError, ValueError):
            return None
        morsel = cookie.get(SESSION_COOKIE)
        return self._principal_from_token(morsel.value if morsel else "")

    def _principal_from_token(self, token: str) -> APIPrincipal | None:
        if not token:
            return None
        session = self.auth.get_session(token)
        return APIPrincipal(user=session.user, session=session) if session else None

    def require(
        self,
        authorization: str | None,
        permission: str | None = None,
        cookie_header: str | None = None,
    ) -> APIPrincipal:
        principal = self.principal_from_header(authorization) or self.principal_from_cookie(cookie_header)
        if principal is None:
            raise PermissionError("Authentication required")
        if permission and not principal.can(permission):
            raise PermissionError("Not authorized for this RF Finder operation")
        return principal

    def logout(self, authorization: str | None, cookie_header: str | None = None) -> bool:
        principal = self.principal_from_header(authorization) or self.principal_from_cookie(cookie_header)
        if principal is None:
            return False
        self.auth.logout(principal.session.token)
        return True
