#!/bin/bash
set -e

echo "Starting API server (tables created automatically on startup)..."
exec uvicorn src.main:app --host 0.0.0.0 --port "${PORT:-8000}"
