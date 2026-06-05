# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**Ananta** — bookkeeping app for an Indian electrical-materials shopkeeper. Workflow:
voice/photo from Telegram → AI extraction (Whisper for voice, Claude Vision for invoice photos) →
business-logic API → PostgreSQL → scheduled daily/weekly Telegram reports + a React dashboard.

## Repo layout

Three independent deployables share one repo:

- `backend/` — FastAPI (`src/main.py`) + SQLAlchemy async + APScheduler. Per-domain packages:
  `products/`, `invoices/`, `sales/`, `payments/`, `stock/`, `reports/`, `imports/` each contain
  `models.py + schemas.py + router.py` (and `service.py` where there is shared logic).
  `src/bot/` is a thin webhook adapter — see deployment notes below.
  `src/shared/storage.py` is the R2-or-local file uploader (used by both `/invoices/ocr` and the
  bulk-import worker — replaces the old `sys.path` hack that pulled `bot/services/storage.py`).
- `bot/` — standalone Telegram bot (`bot/main.py`) used in Docker/polling mode. Handlers in
  `bot/handlers/{voice,photo,text}.py`, AI services in `bot/services/{ocr,nlp,transcriber}.py`,
  HTTP-to-backend client in `bot/services/api_client.py`. Note: `bot/services/storage.py` still
  exists for the polling-mode container; keep it in sync with `backend/src/shared/storage.py`.
- `dashboard/` — Vite + React + TypeScript SPA. Pages: Dashboard, Sales, Customers, Suppliers,
  Invoices, Stock, Payments, Bulk Import, Analytics. Charts use Recharts 3.8.1.

## Two deployment modes (don't conflate them)

The bot can run in two mutually exclusive ways; both are kept in the tree:

1. **Embedded webhook (`render.yaml`, free tier)** — backend includes `src/bot/application.py`
   which imports the same handler modules from `bot/` (it adds `bot/` to `sys.path`) and
   registers a webhook to `POST /bot/webhook`. One Render service runs everything. Triggered when
   `TELEGRAM_BOT_TOKEN` and `APP_BASE_URL` are set.
2. **Polling worker (`docker-compose.yml`)** — `bot/main.py` runs as its own container with
   `app.run_polling()`, talks to the backend over `BACKEND_URL`. Used in DigitalOcean / local
   Docker setups.

Both modes share the handler files in `bot/handlers/` and the services in `bot/services/`.
**Don't split them** — a change to a handler must work under both entry points.

## Common commands

### Backend (FastAPI)
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt          # includes pytest; use requirements.txt for prod
uvicorn src.main:app --reload                # http://localhost:8000, Swagger at /docs
pytest                                       # run tests (config in pyproject.toml)
pytest tests/test_smoke.py::test_health_get  # run a single test
```

Tests live in `backend/tests/`. The `client` fixture in `conftest.py` hits the FastAPI app
in-process via `httpx.ASGITransport` and **does not run lifespan** — so unit tests don't need a
working DB or Telegram token. For DB-touching tests, follow the extension hint in `conftest.py`
(real Postgres only — the schema uses NUMERIC precision and GENERATED columns that SQLite
doesn't reproduce correctly).

Tables are created on startup via `Base.metadata.create_all` in the lifespan handler — Alembic
exists (`alembic/versions/0001_initial_schema.py`) but is **not** run by `start.sh`. If you change
a model, either drop & recreate the dev DB, or write a new Alembic migration and apply it
manually.

### Bot (standalone polling mode)
```bash
cd bot
pip install -r requirements.txt
python main.py                         # needs TELEGRAM_BOT_TOKEN, BACKEND_URL
python test_pipeline.py                # smoke-tests NLP + matcher; OCR/Whisper need API keys
python test_pipeline.py --ocr path/to/invoice.jpg
```

### Dashboard
```bash
cd dashboard
npm install
npm run dev                            # Vite dev server
npm run build                          # tsc + vite build (type errors fail the build)
npm run test                           # vitest in watch mode
npm run test:run                       # vitest single-pass (CI mode)
```

Tests live alongside source as `*.test.ts` / `*.test.tsx`. They run in Node (no DOM) by default;
flip `test.environment` in `vite.config.ts` to `"jsdom"` if you add component tests with
`@testing-library/react`. Test files are excluded from the production `tsc` build via
`tsconfig.json`.

The deployed dashboard talks to the backend through Vercel rewrites in `dashboard/vercel.json`
(`/api/*` → Render URL). The `BACKEND_URL` baked into `vercel.json` is hardcoded — update it if
the Render service is renamed.

### Docker (full stack)
```bash
cp .env.example .env                   # fill in real values
docker compose up --build              # db + backend + bot + dashboard + nginx
docker compose exec backend python seed_demo.py            # 14 days demo data
docker compose exec backend python seed_demo.py --clear    # wipe before client handover
```

## Bulk import (invoices + payments)

`backend/src/imports/` owns the queue-based bulk-import flow used by the
dashboard's `/import` page.

- **Upload**: `POST /imports/upload` (multipart, N files + `kind` form field). Files are
  saved via `shared/storage.upload_image` and recorded as `import_jobs` rows with
  `status="pending"`. CSV alternative for payments: `POST /imports/upload/csv`.
- **Worker**: `imports/worker.py::drain_import_queue` is registered on the same
  `AsyncIOScheduler` as the daily/weekly reports (interval=30s, `max_instances=1`).
  Picks up to 5 pending rows per tick, runs pHash → OCR → fingerprint → dup check.
- **Dedup**: two layers (see `imports/dedup.py`) — exact pHash match, then content
  fingerprint `(supplier_id, invoice_date, round(total), sorted item-set)` with ±1%
  total tolerance. Threshold and rationale: `BULK_IMPORT_PLAN.md` §0 D5.
- **Commit**: `POST /imports/{id}/commit` routes through `invoices/service.py::create_invoice`
  or `payments/service.py::create_payment` — the same code the HTTP `POST /invoices` and
  `POST /payments` routes use. Stock movements happen via the regular path; the 409 contract
  on `invoice_number` is preserved.
- **Suppliers auto-create**: OCR'd vendor names that don't match an existing supplier are
  created with `auto_created=true` (new column on `suppliers`). The dashboard can surface
  these for later manual merge.
- Deps: `ImageHash==4.3.2`, `pypdfium2==4.30.0` (PDF first-page render).

Full design + open decisions: see `BULK_IMPORT_PLAN.md` at repo root.

## Database & money handling

- All money columns are `NUMERIC(12,2)` / `NUMERIC(14,2)`; quantities are `NUMERIC(12,3)`.
  **Never** use `FLOAT` for these. The dashboard explicitly coerces these `Decimal`-string values
  back to `number` (see commits `6b5d8af`, `41204f1`, `8e05dba`) — keep doing that on new fields,
  the JSON serializer emits Decimals as strings.
- `daily_sales`, `purchase_invoice_items` have `line_total` as a `GENERATED ALWAYS AS (qty * price)
  STORED` column. Do not write to it directly.
- Stock is updated through `src/stock/service.py::record_stock_movement` — it inserts a
  `stock_movements` row and atomically updates `products.stock_qty`. Sales and invoice writes must
  go through this helper, not raw `UPDATE products`.
- `purchase_invoices.invoice_number` is `UNIQUE`. The router returns **409** on duplicates (commit
  `86b6293`); preserve that behavior — the bot relies on it to message "Invoice already recorded".

## Async SQLAlchemy gotchas (already wired in `src/db.py`)

- `async_sessionmaker(..., expire_on_commit=False)` is mandatory — without it, accessing any
  attribute after `commit()` triggers a lazy load and crashes in async context.
- The Neon/Supabase URL parsing strips `sslmode=`/`channel_binding=` query params (asyncpg
  rejects them) and supplies an SSL context via `connect_args`. Don't re-introduce those params.
- Connection pool is `NullPool` — Render free tier and Supabase pgbouncer don't like long-lived
  pools.

## AI integration patterns (verified, do not regress)

These are encoded in `bot/services/` and re-stated here because the wrong pattern *looks*
correct:

- Telegram photo → `update.message.photo[-1]` (last element = highest resolution). Never `[0]`.
- Whisper: `client.audio.transcriptions.create(model="whisper-1", file=f, language="hi", response_format="text")`.
  Telegram voice is `.ogg` and Whisper accepts it natively — don't transcode.
- Claude Vision image block: `{"type":"image","source":{"type":"base64","media_type":"image/jpeg","data": <raw_b64>}}`.
  **No `data:image/...;base64,` prefix** in `data`. Image block must come **before** the text block.
- Models: Anthropic `claude-sonnet-4-6` for OCR + NLP, OpenAI `whisper-1` for transcription.
- Scheduler: `AsyncIOScheduler` started/stopped in the FastAPI `lifespan`. Never
  `BackgroundScheduler` in async FastAPI.

## Image storage

`bot/services/storage.py::upload_image` uploads to Cloudflare R2 if all four `R2_*` env vars are
set; otherwise it returns the local path. Reads env directly (not via `settings`) so it works
identically from both deploy modes. When Render is used without R2, images live in `/tmp` and are
wiped on cold start — that's expected, document it for the user before promising photo persistence.

## Things to know before changing things

- The bot is a **single-tenant** app — `SHOP_CHAT_ID` is the only authorized chat. Don't add
  multi-tenant assumptions without asking.
- CORS is wide open (`allow_origins=["*"]`) because the dashboard is proxied through Vercel.
- `/health` answers both `GET` and `HEAD` so UptimeRobot keeps the Render free dyno warm
  (commit `86b6293`).
- `seed_demo.py` is a demo/handover tool — it talks to the live DB via `DATABASE_URL`. The
  `--clear` flag wipes everything; use with care.
- `PLAN.md` is the original implementation plan with full schema/spec; `HANDOVER.md` is the
  DigitalOcean deploy guide; `FREE_TIER_SETUP.md` is the Render+Supabase+Vercel deploy guide.
  Read whichever matches the deployment you're touching.

## Deeper convention docs (read on demand)

These aren't auto-loaded — read the relevant one when you're about to edit code in that area:

- `.claude/rules/api.md` — FastAPI routing/session/error conventions, single-tenant model, CORS.
- `.claude/rules/database.md` — column types, `NUMERIC` for money, GENERATED columns, migration policy, stock-service rule.
- `.claude/rules/frontend.md` — dashboard stack, `toNum` coercion, Recharts gotchas, no state lib / no CSS framework.
- `BULK_IMPORT_PLAN.md` — bulk-import phased plan + dedup design + DO migration notes.
