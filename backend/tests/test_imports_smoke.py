"""Smoke tests for the /imports routes — proves wiring without a DB.

The `client` fixture skips FastAPI lifespan, so there's no DB connection.
We assert that routes are registered and that input validation runs.
"""


async def test_upload_validates_input(client):
    # No files, no `kind` form field → 422 from FastAPI's body parsing.
    r = await client.post("/imports/upload")
    assert r.status_code == 422


async def test_upload_rejects_unknown_kind(client):
    # `kind` present but invalid + still no files → either 400 (our check)
    # or 422 (FastAPI missing-files). Both prove the route is mounted.
    r = await client.post("/imports/upload", data={"kind": "garbage"})
    assert r.status_code in (400, 422)


async def test_routes_registered():
    # Inspect the app directly — proves all five /imports routes exist.
    from src.main import app
    paths = {(tuple(sorted(r.methods)), r.path) for r in app.routes if hasattr(r, "methods")}
    assert (("POST",), "/imports/upload") in paths
    assert (("GET",), "/imports") in paths
    assert (("GET",), "/imports/{job_id}") in paths
    assert (("POST",), "/imports/{job_id}/commit") in paths
    assert (("POST",), "/imports/{job_id}/discard") in paths
