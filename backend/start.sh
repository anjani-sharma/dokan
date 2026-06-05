#!/bin/bash
set -e

# Apply pending migrations first. Adding columns to existing tables can't be
# done by SQLAlchemy's create_all (which only creates missing tables), so the
# lifespan fallback isn't enough — bulk-import revision 0003, for example,
# adds suppliers.auto_created and content_fingerprint columns that the new
# models read on every SELECT.
echo "Applying Alembic migrations..."
alembic upgrade head

echo "Starting API server..."
exec uvicorn src.main:app --host 0.0.0.0 --port "${PORT:-8000}"
