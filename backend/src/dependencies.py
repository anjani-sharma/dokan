from typing import AsyncGenerator

from fastapi import Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def require_token(authorization: str | None = Header(default=None)) -> None:
    """
    Guard mutation endpoints behind the dashboard PIN-derived bearer token.

    When `DASHBOARD_PIN` is empty (dev / local), the gate is disabled and any
    request passes. In prod, the dashboard's axios interceptor sends
    `Authorization: Bearer <token>` derived from the PIN via `auth.issue_token`.
    """
    from src.auth.router import auth_enabled, issue_token
    from src.settings import settings

    if not auth_enabled():
        return

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1].strip()
    expected = issue_token(settings.dashboard_pin)
    from secrets import compare_digest
    if not compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Invalid token")
