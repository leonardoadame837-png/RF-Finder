"""HTTP API for RF Finder."""
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from app.auth.persistent import PersistentAuthService
from app.auth.permissions import has_permission
from app.config import default_config
from app.database.repositories import MeasurementRepository
from app.database.sqlite import Database
from app.devices.manager import DeviceManager
from app.api.routes.live import router as live_router

app = FastAPI(title="RF Finder API", version="0.1.0")
db = Database(default_config.database_path)
auth = PersistentAuthService(db)
devices = DeviceManager(db)
measurements = MeasurementRepository(db)
app.include_router(live_router)


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=12, max_length=256)


class DeviceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    driver: str = Field(min_length=1, max_length=64)
    serial: str | None = Field(default=None, max_length=128)
    center_frequency_hz: float | None = None
    sample_rate_hz: float | None = None


def current_user(authorization: str | None) -> object:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    user = auth.authenticate(authorization[7:].strip())
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


def require(user, permission: str) -> None:
    if not has_permission(user.role, permission):
        raise HTTPException(status_code=403, detail="Insufficient permissions")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/register")
def register(body: Credentials):
    try:
        user = auth.register(body.username, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": user.id, "username": user.username, "role": user.role}


@app.post("/auth/login")
def login(body: Credentials):
    try:
        access, refresh = auth.login(body.username, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer", "expires_in": 900}


@app.post("/auth/logout")
def logout(authorization: str | None = Header(default=None)):
    current_user(authorization)
    auth.logout(authorization[7:].strip())
    return {"status": "ok"}


@app.get("/auth/me")
def me(authorization: str | None = Header(default=None)):
    user = current_user(authorization)
    return {"id": user.id, "username": user.username, "role": user.role}


@app.get("/devices")
def list_devices(authorization: str | None = Header(default=None)):
    user = current_user(authorization)
    require(user, "captures:read")
    return devices.list()


@app.post("/devices")
def create_device(body: DeviceCreate, authorization: str | None = Header(default=None)):
    user = current_user(authorization)
    require(user, "devices:control")
    return devices.register(body.name, body.driver, body.serial, body.center_frequency_hz, body.sample_rate_hz)


@app.get("/measurements")
def list_measurements(limit: int = 100, authorization: str | None = Header(default=None)):
    user = current_user(authorization)
    require(user, "measurements:read")
    return measurements.recent(limit)
