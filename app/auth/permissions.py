"""Role-based authorization rules."""

ROLE_PERMISSIONS = {
    "viewer": {"measurements:read"},
    "analyst": {"measurements:read", "measurements:export", "captures:read"},
    "operator": {"measurements:read", "measurements:export", "captures:read", "devices:control"},
    "admin": {"measurements:read", "measurements:export", "captures:read", "devices:control", "users:manage", "settings:manage"},
    "owner": {"*"},
}


def has_permission(role: str, permission: str) -> bool:
    permissions = ROLE_PERMISSIONS.get(role, set())
    return "*" in permissions or permission in permissions
