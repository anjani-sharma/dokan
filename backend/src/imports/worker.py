"""APScheduler-driven worker that drains the bulk-import queue.

Picks up `import_jobs` rows in status='pending', computes pHash, runs the
OCR pipeline, fingerprints the result, and flips the row to needs_review
or duplicate. The user then confirms via POST /imports/{id}/commit.

Costs (per job): one Anthropic Vision call. Worker caps at 5 jobs per run
to bound spend.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import tempfile
from datetime import date as date_type
from decimal import Decimal, InvalidOperation

from sqlalchemy import select, update

from src.db import AsyncSessionLocal
from src.imports.dedup import (
    compute_invoice_fingerprint,
    compute_payment_fingerprint,
    compute_phash,
    find_duplicate_invoice,
    find_duplicate_payment,
    render_pdf_first_page,
)
from src.imports.models import ImportJob
from src.imports.service import resolve_supplier
from src.shared.storage import fetch_bytes

logger = logging.getLogger(__name__)

BATCH_LIMIT = 5


def _import_ocr():
    """Lazy-import `ocr_document` from the bot package (kept out of backend deps).

    Mirrors `src/bot/application.py` — adds bot/ to sys.path once.
    """
    bot_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "bot")
    )
    if os.path.exists(bot_dir) and bot_dir not in sys.path:
        sys.path.insert(0, bot_dir)
    from services.ocr import ocr_document  # noqa: WPS433
    return ocr_document


def _to_decimal(v) -> Decimal | None:
    if v is None or v == "":
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None


def _to_date(v) -> date_type | None:
    if not v:
        return None
    try:
        return date_type.fromisoformat(str(v))
    except ValueError:
        return None


async def drain_import_queue() -> None:
    """Drain up to BATCH_LIMIT pending jobs.

    Job claim is one atomic `UPDATE ... WHERE id IN (SELECT ... FOR UPDATE
    SKIP LOCKED) RETURNING *`. Two overlapping ticks (or two app instances
    during a zero-downtime redeploy) won't double-process — the second
    UPDATE finds no rows because the first locked them with SKIP LOCKED.
    """
    async with AsyncSessionLocal() as db:
        claim_ids = (
            select(ImportJob.id)
            .where(ImportJob.status == "pending")
            .order_by(ImportJob.id)
            .limit(BATCH_LIMIT)
            .with_for_update(skip_locked=True)
            .scalar_subquery()
        )
        result = await db.execute(
            update(ImportJob)
            .where(ImportJob.id.in_(claim_ids))
            .values(status="extracting")
            .returning(ImportJob)
            .execution_options(synchronize_session=False)
        )
        jobs = list(result.scalars().all())
        await db.commit()

        if not jobs:
            return

        logger.info("import_worker draining %d pending job(s)", len(jobs))
        for job in jobs:
            try:
                await _process_job(db, job)
            except Exception as e:
                logger.exception("import_worker job_id=%s failed", job.id)
                job.status = "failed"
                job.error = f"{type(e).__name__}: {e}"
                await db.commit()


async def _process_job(db, job: ImportJob) -> None:
    # fetch_bytes does a blocking R2 HTTP GET (or local file read) — push it
    # off the event loop so other handlers stay responsive during bulk runs.
    raw = await asyncio.to_thread(fetch_bytes, job.source_path)
    is_pdf = (job.mime_type or "").endswith("pdf") or job.source_path.lower().endswith(".pdf")
    image_bytes = await asyncio.to_thread(render_pdf_first_page, raw) if is_pdf else raw

    # 1. pHash — cheap, deterministic
    try:
        job.image_phash = compute_phash(image_bytes)
    except Exception as e:
        logger.warning("phash failed for job %s: %s", job.id, e)

    # 2. OCR — runs sync, push to a thread so we don't block the event loop
    ocr_document = _import_ocr()
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name
    try:
        # Cost telemetry — Anthropic Vision input tokens ≈ 750 per KB of image.
        # Lets us spot-check spend per bulk run via `grep ocr_call`.
        logger.info(
            "ocr_call job=%s bytes=%d tokens_est=%d",
            job.id, len(image_bytes), len(image_bytes) // 750,
        )
        extracted = await asyncio.to_thread(ocr_document, tmp_path)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    job.extracted = extracted or {}

    doc_type = (extracted or {}).get("type")
    # OCR returned an unrelated doc — mark failed so the user notices.
    if doc_type == "unknown" or not doc_type:
        job.status = "failed"
        job.error = "OCR could not classify the document"
        await db.commit()
        return

    # Job kind ≠ OCR'd type — keep the user's intent (they uploaded under
    # "Invoices") but surface a note in `error` so the review UI can warn.
    if doc_type != job.kind and not (
        doc_type == "payment_slip" and job.kind == "payment"
    ):
        job.error = f"OCR classified as {doc_type}, queued as {job.kind}"

    if job.kind == "invoice":
        await _finish_invoice(db, job, extracted)
    elif job.kind == "payment":
        await _finish_payment(db, job, extracted)
    else:  # pragma: no cover
        job.status = "failed"
        job.error = f"Unknown job kind: {job.kind}"

    await db.commit()


async def _finish_invoice(db, job: ImportJob, extracted: dict) -> None:
    supplier_name = extracted.get("supplier_name") or ""
    supplier_id = await resolve_supplier(db, supplier_name)
    invoice_date = _to_date(extracted.get("invoice_date")) or date_type.today()
    total = _to_decimal(extracted.get("total_amount")) or Decimal("0")
    items = extracted.get("items") or []

    if supplier_id is None:
        job.status = "needs_review"
        job.error = "Supplier name missing or unreadable — please pick one"
        return

    fp = compute_invoice_fingerprint(supplier_id, invoice_date, total, items)
    job.content_fingerprint = fp

    dup = await find_duplicate_invoice(db, job.image_phash, fp, total)
    if dup is not None:
        job.status = "duplicate"
        job.dup_of_invoice_id = dup.id
        return

    # Inject resolved supplier_id into extracted so the dashboard's review
    # form has a starting value even though OCR returned a name not an id.
    extracted["supplier_id"] = supplier_id
    job.extracted = extracted
    job.status = "needs_review"


async def _finish_payment(db, job: ImportJob, extracted: dict) -> None:
    payment_date = _to_date(extracted.get("payment_date")) or date_type.today()
    amount = _to_decimal(extracted.get("amount")) or Decimal("0")
    mode = (extracted.get("payment_mode") or "other").lower()
    ref = extracted.get("transaction_ref")

    fp = compute_payment_fingerprint(payment_date, amount, mode, ref)
    job.content_fingerprint = fp

    dup = await find_duplicate_payment(db, fp, amount)
    if dup is not None:
        job.status = "duplicate"
        job.dup_of_payment_id = dup.id
        return

    job.status = "needs_review"
