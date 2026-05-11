"""
Shared fixtures for backend tests.

The `client` fixture below skips FastAPI lifespan (DB create_all, APScheduler
start, Telegram webhook registration) so unit tests don't need a working
database or a `TELEGRAM_BOT_TOKEN`. Tests that actually touch the DB should add
a separate fixture here that:
  1. Points `DATABASE_URL` at a test database (e.g. `shopdb_test`).
  2. Creates all tables via `Base.metadata.create_all` in setup.
  3. Drops them in teardown.
The schema uses NUMERIC precision and GENERATED ALWAYS AS STORED columns, so
SQLite is NOT a viable substitute — use a real Postgres instance.
"""
import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
