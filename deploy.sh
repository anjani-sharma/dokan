#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# deploy.sh — run this any time you want to update the app
# ─────────────────────────────────────────────────────────────────────────────
set -e
cd /opt/ananta

echo "▶ Pulling latest code..."
git pull origin main

echo "▶ Building containers..."
docker compose build --parallel

echo "▶ Running database migrations..."
docker compose run --rm backend alembic upgrade head

echo "▶ Starting all services..."
docker compose up -d

echo ""
echo "✅ Deployed! Services running:"
docker compose ps --format "table {{.Name}}\t{{.Status}}"
echo ""
echo "View logs:  docker compose logs -f"
echo "Bot logs:   docker compose logs -f bot"
