"""
Smoke tests — proves the test rig is wired up. No DB required.
"""


async def test_health_get(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_health_head(client):
    # /health answers both GET and HEAD so UptimeRobot can keep Render warm.
    r = await client.head("/health")
    assert r.status_code == 200
