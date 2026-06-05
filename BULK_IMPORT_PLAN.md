# Bulk Import + Dedup + DigitalOcean migration — implementation plan

**Status:** draft, awaiting user sign-off on the four open decisions in §0.
**Author:** Claude (orchestrator) — based on parallel discovery of `backend/`, `dashboard/`, `bot/`, and the `imagehash` library docs.
**Last updated:** 2026-05-27

Each phase below is self-contained — a fresh chat with this file + the cited file paths is enough to execute it.

---

## §0 — Open decisions (ANSWER BEFORE EXECUTING)

These were flagged in the original request as decisions the user wants to make, not assumptions for Claude to lock in.

| # | Decision | Default I'd pick | Why |
|---|---|---|---|
| D1 | **Anthropic spend cap** for bulk OCR | Soft cap: log a warning if a single bulk upload exceeds 100 images. No hard block. | One bulk run rarely beats $1. Hard caps lose work. |
| D2 | **Supplier required up front?** | No — auto-create from OCR'd `supplier_name`, mark new suppliers with `auto_created=true` so user can merge later. | Forces less friction; the merge UI is a small follow-up. |
| D3 | **Where does the DB live after DO migration?** | Stay on Supabase free tier. | Saves $15/mo. Supabase is fine for current load. |
| D4 | **PDF support in v1?** | Yes — add `pypdfium2` (Apache, pip-only, no system deps). Render first page only. | Many vendor PDFs in practice; threshold cost is one ~2 MB dep. |
| D5 | **pHash distance threshold** for "same image" | Start at **10** (Hamming, 64-bit phash), surface in review UI so user can tune. | Industry consensus for re-photographed docs. Source: Ben Hoyt, imagededup. |
| D6 | **Refactor `bot/services/storage.py`?** | Yes — move to `backend/src/shared/storage.py`, have bot import from there. Kills the `sys.path` hack. | One-time cleanup, removes a known footgun. |

---

## §1 — Architecture summary (the picture)

```
┌──────────────┐  drag-drop  ┌────────────────────────┐
│ Dashboard    │ ──────────► │ POST /imports          │  (multipart, N files)
│ /import page │             │  → save to R2/local    │
└──────────────┘             │  → insert import_jobs  │  status=pending
       ▲                     │     row per file       │
       │ poll                └────────────┬───────────┘
       │                                  │
       │                                  ▼
       │                  ┌────────────────────────────┐
       │                  │ APScheduler job (every 30s)│
       │                  │  drain_import_queue:       │
       │                  │   for each pending row:    │
       │                  │     ocr_document(path)     │
       │                  │     compute pHash          │
       │                  │     compute fingerprint    │
       │                  │     find dup candidates    │
       │                  │     status=needs_review |  │
       │                  │            duplicate       │
       │                  └────────────┬───────────────┘
       │                               │
       │  GET /imports                 ▼
       │              (extracted data + dup_of FK)
       │
       │ user confirms a row
       │              ┌──────────────────────────────────┐
       └─────────────►│ POST /imports/{id}/commit        │
                      │   → calls invoice_service.create │
                      │      (which calls                │
                      │       record_stock_movement)     │
                      │   → marks job posted             │
                      └──────────────────────────────────┘
```

Key invariants:
- The bulk flow **never** mutates `products.stock_qty` directly — `commit` goes through the existing invoice/payment create paths, which already call `record_stock_movement` (`stock/service.py:10-33`).
- The `import_jobs` table is the source of truth for queue state. No in-process dicts (avoids the `_PENDING` issue we already know about from memory).
- Dedup runs at extract time, not commit time — so review UI shows the warning before the user clicks Post.

---

## §2 — Phase 0: Allowed APIs reference card

Pinned during discovery. Copy from these, don't invent.

**Image hashing — `imagehash` 4.3.2**
```python
from PIL import Image
import imagehash
h = imagehash.phash(Image.open(path))     # 64-bit pHash
hex_str = str(h)                           # 16-char hex — store as CHAR(16)
parsed = imagehash.hex_to_hash(hex_str)    # parse back
distance = h - parsed                      # Hamming distance
```

**PDF first-page render — `pypdfium2`** (Apache-licensed, no system deps)
```python
import pypdfium2 as pdfium
pdf = pdfium.PdfDocument(pdf_bytes_or_path)
page = pdf[0]
pil_image = page.render(scale=2.0).to_pil()   # 2× scale for OCR legibility
```

**OCR — existing, do not rewrite:** `bot/services/ocr.py::ocr_document(image_path: str) -> dict`
- Returns `{type: "invoice"|"payment_slip"|"unknown", confidence, supplier_name, invoice_date, total_amount, items:[{product_name, qty, unit_cost}], …}`
- Uses `claude-sonnet-4-6`, image-block-before-text, base64 with no `data:` prefix. **Don't reimplement.**

**Stock writes — only path allowed:** `backend/src/stock/service.py:10-33::record_stock_movement(db, product_id, movement_type, qty_change, reference_id, reference_type, note)`

**Supplier upsert — already exists:** `POST /products/suppliers/upsert` (`backend/src/products/router.py:36-47`). For backend-internal use, extract the body into `products/service.py::upsert_supplier_by_name(db, name) -> Supplier` so the worker calls it directly instead of self-POSTing.

**Storage — to be moved per D6:** `bot/services/storage.py::upload_image(local_path, prefix) -> str` returns R2 URL or local path. Move to `backend/src/shared/storage.py`, re-export from bot for back-compat.

**Existing FastAPI multipart pattern:** `backend/src/invoices/router.py:307-346` and `backend/src/voice/router.py:37-91`.

**APScheduler pattern:** `backend/src/main.py` lifespan uses `AsyncIOScheduler` + `CronTrigger`. For bulk queue use `IntervalTrigger(seconds=30)` instead.

**Dashboard primitives:**
- `dashboard/src/api/client.ts:333` — `fmt()` for ₹
- `dashboard/src/api/client.ts:608` — multipart upload pattern (`ocrInvoiceUpload`)
- `dashboard/src/components/Modal.tsx` — `createPortal` modal, use as-is
- Page template: `dashboard/src/pages/Invoices.tsx:40-68` — header/filter/table/modal shape

**Anti-patterns — do not regress:**
- ❌ `float` for money/qty
- ❌ Direct `UPDATE products SET stock_qty = …`
- ❌ `BackgroundScheduler` in async FastAPI
- ❌ `data:image/jpeg;base64,…` prefix in the Claude image block
- ❌ Tighter CORS than `["*"]` (Vercel proxy depends on it)
- ❌ New tables without an Alembic migration (Render's `create_all` won't add columns)

---

## §3 — Phase 1: Schema + Alembic migration

**Goal:** add the `import_jobs` table and two columns on `purchase_invoices`. One Alembic revision, applied on DO (where `deploy.sh` runs Alembic).

**Files to create/edit:**

1. New model: `backend/src/imports/models.py`

   ```python
   from datetime import datetime
   from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, JSON
   from sqlalchemy.orm import Mapped, mapped_column
   from sqlalchemy.sql import func
   from src.db import Base

   class ImportJob(Base):
       __tablename__ = "import_jobs"
       id: Mapped[int] = mapped_column(primary_key=True)
       kind: Mapped[str] = mapped_column(String(20))       # "invoice" | "payment"
       status: Mapped[str] = mapped_column(String(20), default="pending")
       # status: pending | extracting | needs_review | duplicate | ready | posted | failed
       source_path: Mapped[str] = mapped_column(Text)      # local path or R2 URL
       original_filename: Mapped[str | None] = mapped_column(Text, nullable=True)
       image_phash: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
       extracted: Mapped[dict | None] = mapped_column(JSON, nullable=True)
       content_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
       dup_of_invoice_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_invoices.id"), nullable=True)
       dup_of_payment_id: Mapped[int | None] = mapped_column(ForeignKey("payments.id"), nullable=True)
       posted_invoice_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_invoices.id"), nullable=True)
       posted_payment_id: Mapped[int | None] = mapped_column(ForeignKey("payments.id"), nullable=True)
       error: Mapped[str | None] = mapped_column(Text, nullable=True)
       created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
       updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
   ```

2. Edit `backend/src/invoices/models.py:10-29` — add two columns:
   ```python
   image_phash: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
   content_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
   ```

3. Edit `backend/src/payments/models.py:10-28` — add one column:
   ```python
   content_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
   ```

4. Edit `backend/src/products/models.py:10-20` (Supplier) — add:
   ```python
   auto_created: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
   ```
   So the review UI can show "this supplier was auto-created from OCR, click to merge".

5. New Alembic revision: `backend/alembic/versions/0003_bulk_import.py`
   - `create_table("import_jobs", …)`
   - `add_column("purchase_invoices", Column("image_phash", String(16), nullable=True))` + index
   - `add_column("purchase_invoices", Column("content_fingerprint", String(64), nullable=True))` + index
   - `add_column("payments", Column("content_fingerprint", String(64), nullable=True))` + index
   - `add_column("suppliers", Column("auto_created", Boolean, nullable=False, server_default="false"))`
   - Symmetric `downgrade()`.

6. Edit `backend/alembic/env.py:20-24` — add `from src.imports import models as imports_models  # noqa` so autogenerate sees the new table.

7. Edit `backend/src/main.py` lifespan — also import `src.imports.models` so `create_all` picks it up on Render (until Render goes away in Phase 6).

**Verification checklist:**
- [ ] `cd backend && alembic upgrade head` succeeds on a fresh local DB.
- [ ] `alembic downgrade -1` runs without errors.
- [ ] `pytest backend/tests/test_smoke.py` passes (in-process, no DB load).
- [ ] `grep -rn "Float" backend/src/imports/` returns nothing.

---

## §4 — Phase 2: Dedup service (pure functions, testable in isolation)

**Goal:** `compute_phash(bytes) -> str`, `compute_invoice_fingerprint(supplier_id, date, total, items) -> str`, and `find_duplicate_invoice(db, phash, fingerprint, total) -> PurchaseInvoice | None`.

**Files to create:**

1. `backend/src/imports/dedup.py`

   ```python
   import hashlib
   from datetime import date
   from decimal import Decimal
   from io import BytesIO
   from PIL import Image
   import imagehash
   from sqlalchemy import select, or_
   from sqlalchemy.ext.asyncio import AsyncSession
   from src.invoices.models import PurchaseInvoice
   from src.payments.models import Payment

   PHASH_HAMMING_THRESHOLD = 10  # see D5

   def compute_phash(image_bytes: bytes) -> str:
       img = Image.open(BytesIO(image_bytes))
       return str(imagehash.phash(img))  # 16-char hex

   def render_pdf_first_page(pdf_bytes: bytes) -> bytes:
       import pypdfium2 as pdfium
       pdf = pdfium.PdfDocument(pdf_bytes)
       pil = pdf[0].render(scale=2.0).to_pil()
       buf = BytesIO()
       pil.save(buf, format="JPEG", quality=85)
       return buf.getvalue()

   def compute_invoice_fingerprint(
       supplier_id: int,
       invoice_date: date,
       total: Decimal,
       items: list[dict],          # [{product_name, qty}, …]
   ) -> str:
       # Sort items by (normalized name, qty) so OCR re-ordering doesn't matter
       norm = sorted(
           (_norm_name(it.get("product_name", "")), float(it.get("qty") or 0))
           for it in items
       )
       payload = f"{supplier_id}|{invoice_date.isoformat()}|{round(float(total))}|{norm}"
       return hashlib.sha256(payload.encode()).hexdigest()[:32]

   def _norm_name(s: str) -> str:
       return "".join(ch for ch in s.lower() if ch.isalnum())

   async def find_duplicate_invoice(
       db: AsyncSession,
       phash: str,
       fingerprint: str,
       total: Decimal,
   ) -> PurchaseInvoice | None:
       # Layer 1: exact phash match (cheap, indexed)
       r = await db.execute(
           select(PurchaseInvoice).where(PurchaseInvoice.image_phash == phash)
       )
       hit = r.scalar_one_or_none()
       if hit:
           return hit

       # Layer 2: same fingerprint, total within ±1%
       r = await db.execute(
           select(PurchaseInvoice).where(
               PurchaseInvoice.content_fingerprint == fingerprint
           )
       )
       cand = r.scalar_one_or_none()
       if cand and _within_pct(float(cand.total_amount), float(total), 1.0):
           return cand

       # Layer 3 (optional): scan recent phashes with Hamming distance ≤ threshold
       # Skip in v1 for cost. Add if false-negative rate is too high in practice.
       return None

   def _within_pct(a: float, b: float, pct: float) -> bool:
       if max(a, b) == 0:
           return True
       return abs(a - b) / max(a, b) * 100 <= pct
   ```

2. Symmetric `find_duplicate_payment(db, phash, fingerprint, amount)` in the same file, fingerprinting on `(payment_date, amount, mode, transaction_ref or "")`.

3. Tests: `backend/tests/test_dedup.py` — pure-function tests for `compute_invoice_fingerprint` (item reordering invariance, total rounding, name normalization) and `_within_pct`. No DB needed.

**Verification checklist:**
- [ ] `pip install ImageHash==4.3.2 pypdfium2` works inside the existing venv.
- [ ] Test: same items in different order produce the same fingerprint.
- [ ] Test: total ₹1000 and ₹1009 with same fingerprint match (within 1%). ₹1000 and ₹1100 don't.
- [ ] Two re-saves of the same JPG (different compression quality) produce phashes within Hamming 5.

**Add to `backend/requirements.txt` and `requirements-dev.txt`:**
```
ImageHash==4.3.2
pypdfium2==4.30.0
```

---

## §5 — Phase 3: Backend bulk-import API + worker

**Goal:** routes to upload, list, commit, and discard import jobs; APScheduler worker that drains the queue.

**Files to create:**

1. `backend/src/imports/router.py` — new domain, mounted at `/imports`:
   - `POST /imports/upload` — accepts `List[UploadFile]` + `kind` form field. For each file: save via `shared/storage.upload_image`, insert `ImportJob` with `status="pending"`, return the IDs.
   - `GET /imports` — paginated list with filter `?status=needs_review|duplicate|posted|failed`. Includes the linked dup-of invoice if any.
   - `GET /imports/{id}` — full row including extracted JSON.
   - `POST /imports/{id}/commit` — accepts edited extracted JSON (user may have corrected fields). Calls the appropriate service:
     - For invoices: extract `supplier_name` → `upsert_supplier_by_name` → build `InvoiceCreate` payload → call `invoice_service.create_invoice(db, payload)`. The existing router logic in `invoices/router.py:42-99` should be **extracted into `invoices/service.py::create_invoice`** so both router and bulk-commit call it. Pattern: the router becomes a 5-line wrapper around the service.
     - For payments: build `PaymentCreate` → call `payment_service.create_payment(db, payload)`. Same extraction pattern as invoices.
     - On success, mark job `status="posted"`, set `posted_invoice_id` or `posted_payment_id`.
   - `POST /imports/{id}/discard` — mark `status="failed"`, set `error="discarded by user"`.

2. `backend/src/imports/worker.py`:
   ```python
   from src.db import AsyncSessionLocal
   from src.imports.models import ImportJob
   from src.imports.dedup import compute_phash, compute_invoice_fingerprint, find_duplicate_invoice
   # ... etc.

   async def drain_import_queue():
       async with AsyncSessionLocal() as db:
           # Pick up to 5 pending jobs at a time (cost-bounded)
           jobs = (await db.execute(
               select(ImportJob).where(ImportJob.status == "pending").limit(5)
           )).scalars().all()
           for job in jobs:
               job.status = "extracting"
               await db.commit()
               try:
                   # ... read bytes (R2 GET or local read), compute phash, run ocr_document, fingerprint, dup-check
                   # ... set extracted, image_phash, content_fingerprint, dup_of_*, status
               except Exception as e:
                   job.status = "failed"
                   job.error = str(e)
               await db.commit()
   ```

3. Edit `backend/src/main.py` lifespan — register the worker as an APScheduler job:
   ```python
   from apscheduler.triggers.interval import IntervalTrigger
   from src.imports.worker import drain_import_queue
   scheduler.add_job(
       drain_import_queue,
       IntervalTrigger(seconds=30),
       id="drain_import_queue",
       replace_existing=True,
       max_instances=1,            # don't double-run
   )
   ```

4. Edit `backend/src/main.py` to mount the router: `app.include_router(imports_router, prefix="/imports", tags=["imports"])`.

5. **Refactor** (per D6): create `backend/src/shared/storage.py`, copy logic from `bot/services/storage.py`. Update bot to `from src.shared.storage import upload_image` (or keep the function in bot but re-export from backend — pick the path that doesn't break the bot's `BACKEND_URL`-only deploy mode).

6. **Refactor** `invoices/router.py` and `payments/router.py` — extract the body of the create endpoint into a `service.py::create_invoice(db, payload) -> PurchaseInvoice` (and same for payments). Router becomes:
   ```python
   @router.post("", response_model=InvoiceOut)
   async def create_invoice_route(body: InvoiceCreate, db: AsyncSession = Depends(get_db)):
       try:
           return await invoice_service.create_invoice(db, body)
       except DuplicateInvoiceNumber:
           raise HTTPException(409, "Invoice already recorded")
   ```
   The existing 409 behavior must be preserved (bot relies on it — see CLAUDE.md).

**Verification checklist:**
- [ ] Upload 3 images via `curl -F` → 3 rows in `import_jobs` with `status="pending"`.
- [ ] Wait 60s → all 3 transitioned to `needs_review` (or `duplicate` if seeded a dup).
- [ ] POST `/imports/{id}/commit` → row 200s, `purchase_invoices` count +1, `stock_movements` count +N.
- [ ] Test the 409 path still works: `curl POST /invoices` with an existing `invoice_number` → 409.
- [ ] Bot smoke test (`python bot/test_pipeline.py`) still passes — refactor didn't break it.

---

## §6 — Phase 4: Dashboard "Bulk import" page

**Goal:** drag-drop upload zone, status table, review-and-post modal.

**Files to create/edit:**

1. New page: `dashboard/src/pages/BulkImport.tsx`. Structure copied from `Invoices.tsx:40-68`:
   - Header: "Bulk import" + a "📤 Upload files" big button that opens the file picker (existing pattern from `InvoiceForm.tsx:42-178`).
   - **Native drag-drop zone** (no `react-dropzone` — codebase has zero deps for it). `onDragOver`, `onDrop`, accept `image/*,application/pdf`, multiple.
   - Table of jobs grouped by status (Pending, Needs review, Duplicates, Posted, Failed) with filter buttons identical to `Invoices.tsx` filter-btn pattern.
   - Each row: thumbnail, supplier, date, total, status badge, action button.
   - Action button opens a `<Modal wide>` (existing `Modal` component, `dashboard/src/components/Modal.tsx`):
     - Left side: image preview
     - Right side: editable extracted fields + items table
     - If `dup_of_invoice_id` is set: red banner "Possible duplicate of Invoice #N from {supplier} on {date}, total {fmt(total)}" with a "View original" link and a "Post anyway" / "Discard" pair of buttons
     - Otherwise: "Post invoice" / "Discard" / "Save edits" buttons
   - Poll `GET /imports?status=pending` every 5s while any pending row is on screen. Stop polling when none.

2. Edit `dashboard/src/api/client.ts` — add interfaces and functions:
   ```typescript
   export interface ImportJob {
     id: number;
     kind: "invoice" | "payment";
     status: string;
     source_path: string;
     original_filename: string | null;
     extracted: any | null;
     dup_of_invoice_id: number | null;
     posted_invoice_id: number | null;
     error: string | null;
     created_at: string;
   }

   export const uploadBulk = (files: File[], kind: "invoice" | "payment") => {
     const fd = new FormData();
     files.forEach(f => fd.append("files", f));
     fd.append("kind", kind);
     return api.post("/imports/upload", fd, {
       headers: { "Content-Type": "multipart/form-data" },
     }).then(r => r.data);
   };

   export const listImports = (status?: string) =>
     api.get("/imports", { params: { status } }).then(r => r.data);

   export const commitImport = (id: number, edited: any) =>
     api.post(`/imports/${id}/commit`, edited).then(r => r.data);

   export const discardImport = (id: number) =>
     api.post(`/imports/${id}/discard`).then(r => r.data);
   ```
   Remember `toNum` on any money fields read from `extracted`.

3. Edit `dashboard/src/App.tsx` — add the route (line 34, before catch-all):
   ```tsx
   <Route path="/import" element={<BulkImport />} />
   ```

4. Edit `dashboard/src/components/Sidebar.tsx` — add nav link:
   ```tsx
   { to: "/import", label: "Bulk Import", icon: IconUpload },
   ```
   Reuse an existing icon if `IconUpload` doesn't exist (check `src/components/Icons.tsx`).

**Verification checklist:**
- [ ] `npm run build` succeeds (tsc strict, no `any` in business logic — `extracted: any` is fine because backend JSON is dynamic).
- [ ] Drag-drop 5 images → all appear as pending rows.
- [ ] Wait → rows flip to "Needs review" automatically.
- [ ] Open review modal → image preview renders, fields editable.
- [ ] Click Post → row moves to "Posted", Invoices page (`/invoices`) shows the new row.
- [ ] Seed a duplicate → red banner appears with link to original.
- [ ] All ₹ display uses `fmt()`. No raw decimal strings visible.

---

## §7 — Phase 5: Payments bulk path

**Goal:** same queue, two new entry points — image batch and CSV.

**Files to create/edit:**

1. Reuse `POST /imports/upload` with `kind=payment`. The worker already branches on `kind` (Phase 3).

2. New endpoint: `POST /imports/upload/csv` — accepts a single CSV `UploadFile`. Required columns: `date,amount,mode,direction,supplier_name?,customer_name?,ref?,note?`. For each row, create an `ImportJob` with `kind="payment"`, `status="needs_review"`, `extracted` pre-filled from the row (no OCR needed). Fingerprint = `(date, amount, mode, ref)`. Dedup against existing payments.

3. Dashboard `BulkImport.tsx` — add a tab/segment "Invoices" vs "Payments" at the top; payments side gets both the drag-drop and a "📋 Upload CSV" button. Provide a downloadable template CSV (static file in `dashboard/public/payments-template.csv`).

**Verification checklist:**
- [ ] Upload a 10-row CSV → 10 rows in `import_jobs`, all `needs_review`, no Anthropic spend.
- [ ] Upload a payment screenshot (UPI) → OCR'd, `payment_mode` and `amount` extracted, surfaced in review.
- [ ] Re-uploading the same CSV → all 10 rows flagged as duplicates.

---

## §8 — Phase 6: DigitalOcean migration

**Goal:** move the embedded-webhook deploy off Render onto a $6 Droplet running `docker-compose.yml`, so APScheduler runs continuously (no Render cold sleeps).

**Pre-flight:**
- Confirm D3 (DB stays on Supabase): the Droplet's `.env` will keep the current `DATABASE_URL`.
- Tell the user to provision the Droplet themselves (root password / SSH key needs human in the loop). Don't try via Bash.

**Steps:**

1. Read existing `docker-compose.yml` and `HANDOVER.md` (the DO deploy guide). Confirm the compose file still matches current backend/bot/dashboard expectations after recent commits.

2. Edit `docker-compose.yml` if needed:
   - Backend container needs `pip install ImageHash pypdfium2` baked in → already covered by adding to `backend/requirements.txt` in Phase 2.
   - Confirm the backend container has write access to a volume for local image storage (fallback when R2 isn't configured). Compose already has this — verify.

3. Update `HANDOVER.md`:
   - Add a "Bulk import" section explaining the queue worker (every 30s).
   - Note that `alembic upgrade head` must run on first deploy and every release (already in `deploy.sh`).
   - Add the new env vars if any (none expected — R2 vars already documented).

4. After droplet is up:
   - SSH in, `git clone`, `cp .env.example .env`, fill values, `bash deploy.sh`.
   - Point Telegram webhook at new domain: `https://api.ananta.example.com/bot/webhook`.
   - Update `dashboard/vercel.json` rewrite target from `ananta-backend-c025.onrender.com` to the new domain. Push dashboard.
   - Verify `/health` returns 200 and UptimeRobot is hitting the new URL.
   - Decommission Render service (don't delete, just suspend, so we can roll back).

**Verification checklist:**
- [ ] `curl https://NEW_DOMAIN/health` → 200.
- [ ] Telegram bot still responds to a test photo.
- [ ] Daily report job fires at 20:00 IST (check logs next day).
- [ ] Bulk upload from dashboard works end-to-end against the new backend.
- [ ] Render service receives zero traffic for 24h, then suspend.

---

## §9 — Phase 7: Final verification

1. **Grep guards** — run these and confirm zero hits:
   ```bash
   grep -rn "Float" backend/src/imports/ backend/src/invoices/models.py backend/src/payments/models.py
   grep -rn "BackgroundScheduler" backend/src/
   grep -rn "data:image" bot/services/ocr.py backend/src/
   grep -rn "UPDATE products SET stock_qty" backend/src/
   ```

2. **Behavior regressions** — re-run from PLAN.md / CLAUDE.md:
   - `POST /invoices` with duplicate `invoice_number` → still 409.
   - `/health` answers both GET and HEAD.
   - CORS still `["*"]`.
   - Bot photo handler still works (memory's `_PENDING` issue is unchanged, that's a separate cleanup).

3. **Cost telemetry** — add a log line in `worker.py` per OCR call: `logger.info("ocr_call job=%s tokens_est=%d", job.id, len(image_bytes) // 750)`. Lets us track Anthropic spend per bulk run.

4. **Manual happy-path test** with 20 mixed invoices (some real dups, some PDFs):
   - Upload, wait, review, post.
   - Verify stock movements match expected counts.
   - Verify dup detection caught the seeded duplicates.

5. Update `CLAUDE.md`:
   - New domain in "Repo layout" section.
   - Mention `backend/src/imports/` and `backend/src/shared/storage.py`.
   - Note that suppliers can be auto-created and have an `auto_created` flag.

---

## §10 — Things explicitly NOT done in this plan (deferred)

- **Supplier merge UI** — the `auto_created` flag is set, but the actual "merge supplier A into supplier B" flow is a separate small feature.
- **Hamming-distance phash scan (Layer 3)** — only exact phash and fingerprint match in v1. Add later if false-negative rate is annoying.
- **Bot-side bulk upload** — Telegram is one-photo-at-a-time. If a user sends 10 photos, they go through the existing single-shot path, not the new queue. Out of scope.
- **OCR for vendor GSTIN / address** — would improve supplier matching accuracy, but the prompt change risks regressing the existing happy path. Defer.
- **Real-time progress UI** — dashboard polls every 5s, no websockets. Good enough.
- **Multi-tenant** — explicitly out of scope per original ask. Dokane will reimplement.

---

## Execution order

1. Answer §0 D1–D6.
2. Run Phase 1 (schema). Stop, verify migration is reversible.
3. Run Phase 2 (dedup service). Stop, run unit tests.
4. Run Phase 3 (backend API + worker). Stop, manual smoke with curl.
5. Run Phase 4 (dashboard page). Stop, manual smoke in browser.
6. Run Phase 5 (payments). Stop, manual smoke.
7. **Pause** — get user sign-off before Phase 6. The DO migration is a deploy operation that needs human hands on the droplet provisioning step.
8. Run Phase 6 (DO migration) with user.
9. Run Phase 7 (verification + docs).
