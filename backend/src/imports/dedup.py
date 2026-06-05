"""Duplicate detection for bulk-imported invoices and payments.

Two-layer check:
  1. Image perceptual hash (pHash) — catches re-uploads of the same photo.
  2. Content fingerprint — order-independent hash of normalized fields;
     catches re-scans where the picture changed but the underlying document
     is the same.

The fingerprint is intentionally lossy: round totals to whole rupees,
strip non-alphanumerics from item names, and sort items so OCR re-ordering
doesn't matter. We then accept a ±1% tolerance on `total_amount` at lookup
time because OCR occasionally misreads a paise digit.
"""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal
from io import BytesIO

import imagehash
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.invoices.models import PurchaseInvoice
from src.payments.models import Payment

PHASH_HAMMING_THRESHOLD = 10  # see BULK_IMPORT_PLAN.md §0 D5
TOTAL_TOLERANCE_PCT = 1.0


def compute_phash(image_bytes: bytes) -> str:
    """64-bit pHash as 16-char hex. Raises on undecodable bytes."""
    img = Image.open(BytesIO(image_bytes))
    return str(imagehash.phash(img))


def render_pdf_first_page(pdf_bytes: bytes) -> bytes:
    """First page of a PDF as JPEG bytes (for OCR + pHash)."""
    import pypdfium2 as pdfium  # heavy; defer import

    pdf = pdfium.PdfDocument(pdf_bytes)
    pil = pdf[0].render(scale=2.0).to_pil()
    buf = BytesIO()
    pil.convert("RGB").save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _norm_name(s: str) -> str:
    return "".join(ch for ch in (s or "").lower() if ch.isalnum())


def compute_invoice_fingerprint(
    supplier_id: int,
    invoice_date: date,
    total: Decimal | float | int,
    items: list[dict],
) -> str:
    """Order-independent sha256 prefix over (supplier, date, rounded total, sorted items).

    `items` is a list of dicts with a `qty` field and a name under one of
    `product_name`, `product_name_raw`, or `name`. Accepting all three lets
    both the worker (which sees OCR output keyed `product_name`) and the
    HTTP commit path (which dumps `InvoiceItemCreate.product_name_raw`) hash
    to the same value.
    """
    norm = sorted(
        (
            _norm_name(
                it.get("product_name")
                or it.get("product_name_raw")
                or it.get("name")
                or ""
            ),
            float(it.get("qty") or 0),
        )
        for it in items
    )
    payload = f"{supplier_id}|{invoice_date.isoformat()}|{round(float(total))}|{norm}"
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def compute_payment_fingerprint(
    payment_date: date,
    amount: Decimal | float | int,
    mode: str,
    transaction_ref: str | None,
) -> str:
    payload = (
        f"{payment_date.isoformat()}|{round(float(amount), 2)}|"
        f"{(mode or '').lower()}|{(transaction_ref or '').strip()}"
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def _within_pct(a: float, b: float, pct: float) -> bool:
    hi = max(a, b)
    if hi == 0:
        return True
    return abs(a - b) / hi * 100 <= pct


def _hamming_hex(a: str, b: str) -> int:
    """Hamming distance between two 16-char (64-bit) hex pHashes."""
    return bin(int(a, 16) ^ int(b, 16)).count("1")


# Cap on how many recent invoice phashes we pull into Python to compare.
# Single-tenant shop accumulates a few thousand invoices a year — a bounded
# scan keeps the lookup O(1) instead of growing forever, at the cost of
# possibly missing a duplicate against an invoice older than the cap.
_PHASH_SCAN_LIMIT = 1000


async def find_duplicate_invoice(
    db: AsyncSession,
    phash: str | None,
    fingerprint: str | None,
    total: Decimal | float | int,
) -> PurchaseInvoice | None:
    """Return an existing invoice that matches by phash or fingerprint, else None."""
    if phash:
        # Layer 1: exact phash match — cheap, indexed, catches byte-identical re-uploads.
        r = await db.execute(
            select(PurchaseInvoice).where(PurchaseInvoice.image_phash == phash)
        )
        hit = r.scalars().first()
        if hit is not None:
            return hit

        # Layer 2: Hamming distance ≤ threshold — catches the same document
        # photographed twice (different angle/lighting → different bytes).
        # Distance can't be expressed in SQL without a bit-count extension,
        # so we scan the recent _PHASH_SCAN_LIMIT rows in Python.
        r = await db.execute(
            select(PurchaseInvoice)
            .where(PurchaseInvoice.image_phash.is_not(None))
            .order_by(PurchaseInvoice.id.desc())
            .limit(_PHASH_SCAN_LIMIT)
        )
        for cand in r.scalars().all():
            try:
                if _hamming_hex(phash, cand.image_phash) <= PHASH_HAMMING_THRESHOLD:
                    return cand
            except (TypeError, ValueError):
                continue

    if fingerprint:
        r = await db.execute(
            select(PurchaseInvoice).where(
                PurchaseInvoice.content_fingerprint == fingerprint
            )
        )
        for cand in r.scalars().all():
            if _within_pct(float(cand.total_amount), float(total), TOTAL_TOLERANCE_PCT):
                return cand

    return None


async def find_duplicate_payment(
    db: AsyncSession,
    fingerprint: str | None,
    amount: Decimal | float | int,
) -> Payment | None:
    if not fingerprint:
        return None
    r = await db.execute(
        select(Payment).where(Payment.content_fingerprint == fingerprint)
    )
    for cand in r.scalars().all():
        if _within_pct(float(cand.amount), float(amount), TOTAL_TOLERANCE_PCT):
            return cand
    return None
