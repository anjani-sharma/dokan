#!/bin/bash
set -eo pipefail

echo "================ start.sh ================="
echo "PWD: $(pwd)"
echo "Python: $(python --version 2>&1)"
echo "Alembic: $(alembic --version 2>&1)"
echo "============================================"

# One-time bootstrap: the deployed DB was originally seeded by SQLAlchemy's
# create_all (no alembic_version table). Stamp it at the last pre-bulk-import
# revision so `upgrade head` applies only the new ones. Idempotent on
# already-versioned DBs.
#
# Detection uses asyncpg directly — importing alembic.config inside a heredoc
# that runs with cwd=backend/ would resolve to the local alembic/ package
# (env.py + migrations) and fail with ModuleNotFoundError.
BOOTSTRAP_OUT=$(python <<'PY' 2>&1
import asyncio, os, re, ssl, sys
import asyncpg

raw = os.environ.get("DATABASE_URL", "")
url = raw
if url.startswith("postgresql+asyncpg://"):
    url = "postgres://" + url[len("postgresql+asyncpg://"):]
elif url.startswith("postgresql://"):
    url = "postgres://" + url[len("postgresql://"):]
url = re.sub(r"[?&](sslmode|channel_binding)=[^&]*", "", url).rstrip("?&")


async def check():
    ssl_ctx = (
        ssl.create_default_context()
        if ("supabase" in url or "neon.tech" in url)
        else None
    )
    conn = await asyncpg.connect(url, ssl=ssl_ctx)
    try:
        av = await conn.fetchval("SELECT to_regclass('alembic_version')")
        if av is None:
            return ("missing", None, None)
        rev = await conn.fetchval("SELECT version_num FROM alembic_version LIMIT 1")
        # Probe whether the column the new model needs is already there.
        col_exists = await conn.fetchval(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='suppliers' AND column_name='auto_created'"
        )
        return ("present", rev, bool(col_exists))
    finally:
        await conn.close()


try:
    state, rev, has_col = asyncio.run(check())
    print(f"DB_STATE state={state} rev={rev} suppliers.auto_created_exists={has_col}")
except Exception as e:
    print(f"DB_STATE_ERROR {type(e).__name__}: {e}", file=sys.stderr)
    raise
PY
)
echo "$BOOTSTRAP_OUT"

# Parse the state line so we can branch in shell.
DB_STATE=$(echo "$BOOTSTRAP_OUT" | grep -oE 'state=[a-z]+' | cut -d= -f2 || true)

if [ "$DB_STATE" = "missing" ]; then
  echo "==> alembic_version absent — stamping at 0002"
  alembic stamp 0002
elif [ "$DB_STATE" = "present" ]; then
  echo "==> alembic_version present — leaving stamp alone"
else
  echo "==> Could not determine DB state; aborting before migrations"
  exit 1
fi

echo "==> alembic current (before upgrade):"
alembic current
echo "==> Applying Alembic migrations..."
alembic upgrade head
echo "==> alembic current (after upgrade):"
alembic current

# Last-line sanity: did we actually end up with the column the new model reads?
python <<'PY' 2>&1
import asyncio, os, re, ssl, sys
import asyncpg

raw = os.environ.get("DATABASE_URL", "")
url = raw
if url.startswith("postgresql+asyncpg://"):
    url = "postgres://" + url[len("postgresql+asyncpg://"):]
elif url.startswith("postgresql://"):
    url = "postgres://" + url[len("postgresql://"):]
url = re.sub(r"[?&](sslmode|channel_binding)=[^&]*", "", url).rstrip("?&")

async def verify():
    ssl_ctx = (
        ssl.create_default_context()
        if ("supabase" in url or "neon.tech" in url)
        else None
    )
    conn = await asyncpg.connect(url, ssl=ssl_ctx)
    try:
        ok = await conn.fetchval(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='suppliers' AND column_name='auto_created'"
        )
        return bool(ok)
    finally:
        await conn.close()

if asyncio.run(verify()):
    print("POST_MIGRATE_OK suppliers.auto_created exists")
else:
    print("POST_MIGRATE_FAIL suppliers.auto_created still missing", file=sys.stderr)
    sys.exit(2)
PY

echo "==> Starting API server..."
exec uvicorn src.main:app --host 0.0.0.0 --port "${PORT:-8000}"
