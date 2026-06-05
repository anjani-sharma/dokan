#!/bin/bash
set -e

# One-time bootstrap: the deployed DB was originally seeded by SQLAlchemy's
# create_all (no alembic_version table). Stamp it at the last pre-bulk-import
# revision so `upgrade head` applies only the new ones. Idempotent on
# already-versioned DBs.
#
# Detection uses asyncpg directly — importing alembic.config inside a heredoc
# that runs with cwd=backend/ would resolve to the local alembic/ package
# (env.py + migrations) and fail with ModuleNotFoundError.
HAS_AV=$(python <<'PY'
import asyncio, os, re, ssl
import asyncpg

raw = os.environ.get("DATABASE_URL", "")
url = raw
if url.startswith("postgresql+asyncpg://"):
    url = "postgres://" + url[len("postgresql+asyncpg://"):]
elif url.startswith("postgresql://"):
    url = "postgres://" + url[len("postgresql://"):]
url = re.sub(r"[?&](sslmode|channel_binding)=[^&]*", "", url).rstrip("?&")

async def check() -> bool:
    ssl_ctx = (
        ssl.create_default_context()
        if ("supabase" in url or "neon.tech" in url)
        else None
    )
    conn = await asyncpg.connect(url, ssl=ssl_ctx)
    try:
        return (await conn.fetchval("SELECT to_regclass('alembic_version')")) is not None
    finally:
        await conn.close()

print("1" if asyncio.run(check()) else "0")
PY
)

if [ "$HAS_AV" != "1" ]; then
  echo "alembic_version missing — stamping at 0002 (DB was create_all'd)"
  alembic stamp 0002
else
  echo "alembic_version present — skipping bootstrap stamp"
fi

echo "Applying Alembic migrations..."
alembic upgrade head

echo "Starting API server..."
exec uvicorn src.main:app --host 0.0.0.0 --port "${PORT:-8000}"
