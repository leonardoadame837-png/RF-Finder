"""Live spectrum endpoints for the field UI.

The endpoint is intentionally simulator-backed until an authorized capture
worker is attached to physical SDR hardware.
"""
from fastapi import APIRouter, Header, HTTPException
from app.auth.permissions import has_permission
from app.api.server import current_user

router = APIRouter(prefix="/live", tags=["live"])

@router.get("/status")
def status(authorization: str | None = Header(default=None)):
    user = current_user(authorization)
    if not has_permission(user.role, "measurements:read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return {"running": False, "source": "simulator", "message": "Capture worker not started"}
