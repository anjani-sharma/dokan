"""
Dashboard PIN gate.

`POST /auth/login` accepts a 4-digit PIN and returns a deterministic bearer
token (HMAC of PIN + server secret). The token is then required on every
mutating endpoint (see `require_token` in `src/dependencies.py`).

GET endpoints stay open so UptimeRobot, the Telegram bot, and the existing
report-trigger flow keep working without auth headers.
"""
import hmac
from hashlib import sha256
from secrets import compare_digest

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.settings import settings

router = APIRouter()


class LoginIn(BaseModel):
    pin: str = Field(..., min_length=1, max_length=12)


class LoginOut(BaseModel):
    token: str


def issue_token(pin: str) -> str:
    return hmac.new(
        settings.dashboard_secret.encode("utf-8"),
        pin.encode("utf-8"),
        sha256,
    ).hexdigest()


def auth_enabled() -> bool:
    return bool(settings.dashboard_pin)


@router.post("/login", response_model=LoginOut)
async def login(body: LoginIn):
    if not auth_enabled():
        # When no PIN is configured, accept any login and hand out a token so
        # the dashboard auth flow still works in dev without env vars.
        return LoginOut(token=issue_token(body.pin))
    if not compare_digest(body.pin, settings.dashboard_pin):
        raise HTTPException(status_code=401, detail="Invalid PIN")
    return LoginOut(token=issue_token(settings.dashboard_pin))
