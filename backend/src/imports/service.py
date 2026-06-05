"""Helpers for the bulk-import flow — file intake, commit, discard.

The router stays thin; this module owns the side effects (disk + DB).
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.imports.dedup import compute_invoice_fingerprint, compute_payment_fingerprint
from src.imports.models import ImportJob
from src.invoices.schemas import InvoiceCreate
from src.invoices.service import DuplicateInvoiceNumber, create_invoice as create_invoice_service
from src.payments.schemas import PaymentCreate
from src.payments.service import create_payment as create_payment_service
from src.products.service import upsert_supplier_by_name
from src.settings import settings
from src.shared.storage import upload_image

logger = logging.getLogger(__name__)

ALLOWED_EXTS = ("jpg", "jpeg", "png", "webp", "pdf")


def _safe_ext(filename: str | None, content_type: str | None) -> str:
    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext in ALLOWED_EXTS:
            return ext
    if content_type:
        ct = content_type.lower()
        if "pdf" in ct:
            return "pdf"
        if "png" in ct:
            return "png"
        if "webp" in ct:
            return "webp"
    return "jpg"


async def queue_file(
    db: AsyncSession,
    *,
    kind: str,
    filename: str | None,
    content_type: str | None,
    contents: bytes,
) -> ImportJob:
    """Save the upload to disk (or R2) and insert an `ImportJob` row."""
    if kind not in ("invoice", "payment"):
        raise ValueError(f"Unknown kind: {kind}")

    ext = _safe_ext(filename, content_type)
    if ext not in ALLOWED_EXTS:
        raise ValueError(f"Unsupported file type: .{ext}")

    images_dir = settings.images_dir
    os.makedirs(images_dir, exist_ok=True)
    local_path = os.path.join(images_dir, f"import-{uuid.uuid4().hex}.{ext}")
    with open(local_path, "wb") as out:
        out.write(contents)

    # Push to R2 if configured. If not, the local path persists for the worker.
    try:
        stored_path = upload_image(local_path, prefix=f"imports/{kind}s")
    except Exception as e:  # pragma: no cover — R2 failures are noisy in tests
        logger.warning("R2 upload skipped (%s) — keeping local path", e)
        stored_path = local_path

    job = ImportJob(
        kind=kind,
        status="pending",
        source_path=stored_path,
        original_filename=filename,
        mime_type=content_type,
    )
    db.add(job)
    await db.flush()
    return job


async def commit_invoice_job(
    db: AsyncSession,
    job: ImportJob,
    body: InvoiceCreate,
) -> int:
    """Run the user-confirmed invoice through the regular create path.

    Invoice creation and job-status update share one transaction — if the
    commit fails mid-way the whole thing rolls back, no orphaned "posted"
    invoice with a `needs_review` job. The unique-invoice-number check uses
    a savepoint inside `create_invoice_service`, so on DuplicateInvoiceNumber
    we can still record the failure on the job and commit it.
    """
    fp = compute_invoice_fingerprint(
        body.supplier_id,
        body.invoice_date,
        body.total_amount,
        [item.model_dump() for item in body.items],
    )
    try:
        invoice = await create_invoice_service(
            db,
            body,
            image_phash=job.image_phash,
            content_fingerprint=fp,
        )
    except DuplicateInvoiceNumber:
        job.status = "needs_review"
        job.error = f"Invoice number {body.invoice_number} already exists"
        await db.commit()
        raise

    job.status = "posted"
    job.posted_invoice_id = invoice.id
    job.content_fingerprint = fp
    await db.commit()
    return invoice.id


async def commit_payment_job(
    db: AsyncSession,
    job: ImportJob,
    body: PaymentCreate,
) -> int:
    fp = compute_payment_fingerprint(
        body.payment_date,
        body.amount,
        body.payment_mode,
        body.transaction_ref,
    )
    payment = await create_payment_service(db, body, content_fingerprint=fp)

    job.status = "posted"
    job.posted_payment_id = payment.id
    job.content_fingerprint = fp
    await db.commit()
    return payment.id


async def discard_job(db: AsyncSession, job: ImportJob, reason: str = "discarded by user") -> None:
    job.status = "failed"
    job.error = reason
    await db.commit()


async def resolve_supplier(db: AsyncSession, name: str | None) -> int | None:
    """For the worker: turn an OCR'd supplier_name into a `suppliers.id`."""
    if not name:
        return None
    supplier = await upsert_supplier_by_name(db, name, auto_created=True)
    return supplier.id if supplier else None


async def queue_payment_csv_rows(
    db: AsyncSession,
    rows: list[dict],
) -> list[ImportJob]:
    """Create one `ImportJob` per CSV row (no OCR — extracted is the row itself).

    Expected row keys: date, amount, mode, direction, ref, note, supplier_name, customer_name.
    Status starts at `needs_review` (already classified) so the worker skips them.
    """
    from src.imports.dedup import (
        compute_payment_fingerprint,
        find_duplicate_payment,
    )

    out: list[ImportJob] = []
    for raw in rows:
        try:
            payment_date = date.fromisoformat(str(raw.get("date") or "").strip())
        except (ValueError, TypeError):
            payment_date = date.today()

        try:
            amount = Decimal(str(raw.get("amount") or "0"))
        except Exception:
            amount = Decimal("0")

        mode = (raw.get("mode") or "other").strip().lower()
        direction = (raw.get("direction") or "outflow").strip().lower()
        ref = (raw.get("ref") or "").strip() or None
        note = (raw.get("note") or "").strip() or None

        supplier_name = (raw.get("supplier_name") or "").strip() or None
        customer_name = (raw.get("customer_name") or "").strip() or None

        extracted = {
            "type": "payment_slip",
            "payment_date": payment_date.isoformat(),
            "amount": str(amount),
            "payment_mode": mode,
            "direction": direction,
            "transaction_ref": ref,
            "note": note,
            "supplier_name": supplier_name,
            "customer_name": customer_name,
        }

        fp = compute_payment_fingerprint(payment_date, amount, mode, ref)
        dup = await find_duplicate_payment(db, fp, amount)

        job = ImportJob(
            kind="payment",
            status="duplicate" if dup else "needs_review",
            source_path=f"csv:row#{len(out) + 1}",
            original_filename=raw.get("_source_filename"),
            mime_type="text/csv",
            extracted=extracted,
            content_fingerprint=fp,
            dup_of_payment_id=dup.id if dup else None,
        )
        db.add(job)
        out.append(job)

    await db.flush()
    return out
