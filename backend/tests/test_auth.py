"""
PIN-gate tests for the dashboard auth.

We toggle `settings.dashboard_pin` at runtime so we don't need env-var plumbing
in the test rig. None of these tests touch the DB.
"""
import pytest

from src.auth.router import issue_token
from src.settings import settings


@pytest.fixture
def with_pin():
    """Enable the gate with a known PIN for the duration of a test."""
    prev_pin = settings.dashboard_pin
    settings.dashboard_pin = "4242"
    yield "4242"
    settings.dashboard_pin = prev_pin


@pytest.fixture
def without_pin():
    prev_pin = settings.dashboard_pin
    settings.dashboard_pin = ""
    yield
    settings.dashboard_pin = prev_pin


async def test_login_returns_token(client, with_pin):
    r = await client.post("/auth/login", json={"pin": with_pin})
    assert r.status_code == 200
    assert r.json()["token"] == issue_token(with_pin)


async def test_login_wrong_pin_rejected(client, with_pin):
    r = await client.post("/auth/login", json={"pin": "0000"})
    assert r.status_code == 401


async def test_login_when_disabled_accepts_any(client, without_pin):
    # Dev mode: empty PIN means the gate is off and login always succeeds.
    r = await client.post("/auth/login", json={"pin": "anything"})
    assert r.status_code == 200
    assert "token" in r.json()


async def test_mutation_requires_token_when_pin_set(client, with_pin):
    # No Authorization header → 401, regardless of body validity.
    r = await client.post("/sales/daily", json={})
    assert r.status_code == 401


async def test_mutation_with_bad_token_rejected(client, with_pin):
    r = await client.post(
        "/sales/daily",
        json={},
        headers={"Authorization": "Bearer wrong"},
    )
    assert r.status_code == 401


async def test_mutation_when_disabled_does_not_require_token(client, without_pin):
    # Body is invalid (422) but we should *not* see 401 — proves the gate is off.
    r = await client.post("/sales/daily", json={})
    assert r.status_code != 401


async def test_get_endpoints_stay_open(client, with_pin):
    # GETs must keep working unauthenticated (UptimeRobot, bot reads, etc.).
    r = await client.get("/health")
    assert r.status_code == 200
