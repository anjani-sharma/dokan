import logging
import os
import sys
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.dependencies import get_db, require_token
from src.invoices.models import PurchaseInvoice, PurchaseInvoiceItem
from src.invoices.schemas import (
    InvoiceCreate, InvoiceItemCreate, InvoiceOut, InvoiceUpdate,
)
from src.invoices.service import DuplicateInvoiceNumber, create_invoice as create_invoice_service
from src.products.service import upsert_product_by_name
from src.settings import settings
from src.stock.service import record_stock_movement, reverse_stock_movement

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=list[InvoiceOut])
async def list_invoices(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(PurchaseInvoice)
        .options(selectinload(PurchaseInvoice.items))
        .order_by(PurchaseInvoice.invoice_date.desc())
    )
    if status:
        q = q.where(PurchaseInvoice.status == status)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/duplicates", response_model=list[list[InvoiceOut]])
async def find_duplicate_invoices(db: AsyncSession = Depends(get_db)):
    """Group existing invoices by (supplier_id, invoice_date, rounded total).
    Returns each cluster with more than one row — that's the dedup signal
    the worker uses for new uploads, applied retroactively so the user can
    inspect and delete the extras.
    """
    result = await db.execute(
        select(PurchaseInvoice)
        .options(selectinload(PurchaseInvoice.items))
        .order_by(PurchaseInvoice.invoice_date.desc(), PurchaseInvoice.id.desc())
    )
    invoices = list(result.scalars().all())

    # Bucket by (supplier_id, invoice_date, ₹-rounded total). Single-tenant
    # so a Python-side group is fine — invoice count is in the thousands at
    # most.
    buckets: dict[tuple[int, str, int], list[PurchaseInvoice]] = {}
    for inv in invoices:
        key = (inv.supplier_id, inv.invoice_date.isoformat(), round(float(inv.total_amount)))
        buckets.setdefault(key, []).append(inv)

    return [group for group in buckets.values() if len(group) > 1]


@router.post("", response_model=InvoiceOut, status_code=201, dependencies=[Depends(require_token)])
async def create_invoice(body: InvoiceCreate, db: AsyncSession = Depends(get_db)):
    try:
        invoice = await create_invoice_service(db, body)
    except DuplicateInvoiceNumber:
        raise HTTPException(status_code=409, detail=f"Invoice {body.invoice_number} already exists")
    await db.commit()
    # commit + an identity-mapped instance can leave items unloaded for
    # the response serializer even after selectinload — refresh forces it.
    await db.refresh(invoice, attribute_names=["items"])
    return invoice


@router.get("/{invoice_id}", response_model=InvoiceOut)
async def get_invoice(invoice_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PurchaseInvoice)
        .options(selectinload(PurchaseInvoice.items))
        .where(PurchaseInvoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.put("/{invoice_id}", response_model=InvoiceOut, dependencies=[Depends(require_token)])
async def update_invoice(invoice_id: int, body: InvoiceUpdate, db: AsyncSession = Depends(get_db)):
    invoice = await db.get(PurchaseInvoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(invoice, field, value)
    # Auto-set status based on paid_amount
    if invoice.paid_amount >= invoice.total_amount:
        invoice.status = "paid"
    elif invoice.paid_amount > 0:
        invoice.status = "partial"
    await db.commit()
    # Force-load items on the in-session instance. A bare refresh without
    # attribute_names skips relationships; a re-select can hit the same
    # identity-map instance and leave items unloaded.
    await db.refresh(invoice, attribute_names=["items"])
    return invoice


@router.delete("/{invoice_id}", status_code=204, dependencies=[Depends(require_token)])
async def delete_invoice(invoice_id: int, db: AsyncSession = Depends(get_db)):
    """Delete an invoice and reverse the stock movements its items caused."""
    result = await db.execute(
        select(PurchaseInvoice)
        .options(selectinload(PurchaseInvoice.items))
        .where(PurchaseInvoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    for item in invoice.items:
        if item.product_id and item.qty:
            await reverse_stock_movement(
                db,
                product_id=item.product_id,
                qty_change=-item.qty,
                reference_id=invoice.id,
                reference_type="purchase_invoice_delete",
            )
    await db.delete(invoice)
    await db.commit()


# ── Invoice line-item CRUD ──────────────────────────────────────────────────
#
# Used by the dashboard's invoice edit panel so individual rows can be added,
# corrected, or removed after the invoice has been saved. Every change keeps
# stock_qty in sync via record/reverse_stock_movement.

async def _load_invoice(db: AsyncSession, invoice_id: int) -> PurchaseInvoice:
    result = await db.execute(
        select(PurchaseInvoice)
        .options(selectinload(PurchaseInvoice.items))
        .where(PurchaseInvoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.post(
    "/{invoice_id}/items",
    response_model=InvoiceOut,
    status_code=201,
    dependencies=[Depends(require_token)],
)
async def add_item(invoice_id: int, body: InvoiceItemCreate, db: AsyncSession = Depends(get_db)):
    invoice = await _load_invoice(db, invoice_id)

    product_id = body.product_id
    if not product_id and body.product_name_raw:
        product = await upsert_product_by_name(
            db, body.product_name_raw, default_cost=body.unit_cost
        )
        if product:
            product_id = product.id

    item = PurchaseInvoiceItem(
        purchase_invoice_id=invoice.id,
        product_id=product_id,
        product_name_raw=body.product_name_raw,
        qty=body.qty,
        unit_cost=body.unit_cost,
    )
    db.add(item)
    if product_id:
        await record_stock_movement(
            db,
            product_id=product_id,
            movement_type="purchase",
            qty_change=body.qty,
            reference_id=invoice.id,
            reference_type="purchase_invoice_item_add",
        )
    await db.commit()
    return await _load_invoice(db, invoice_id)


@router.put(
    "/{invoice_id}/items/{item_id}",
    response_model=InvoiceOut,
    dependencies=[Depends(require_token)],
)
async def update_item(
    invoice_id: int,
    item_id: int,
    body: InvoiceItemCreate,
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(PurchaseInvoiceItem, item_id)
    if not item or item.purchase_invoice_id != invoice_id:
        raise HTTPException(status_code=404, detail="Item not found")

    old_qty = item.qty
    old_product_id = item.product_id

    new_product_id = body.product_id
    if not new_product_id and body.product_name_raw:
        product = await upsert_product_by_name(
            db, body.product_name_raw, default_cost=body.unit_cost
        )
        if product:
            new_product_id = product.id

    # Reverse the old movement, then apply the new — handles product changes
    # (e.g. user renamed a line item to a different product).
    if old_product_id and old_qty:
        await reverse_stock_movement(
            db,
            product_id=old_product_id,
            qty_change=-old_qty,
            reference_id=invoice_id,
            reference_type="purchase_invoice_item_edit_undo",
        )
    if new_product_id and body.qty:
        await record_stock_movement(
            db,
            product_id=new_product_id,
            movement_type="purchase",
            qty_change=body.qty,
            reference_id=invoice_id,
            reference_type="purchase_invoice_item_edit",
        )

    item.product_id = new_product_id
    item.product_name_raw = body.product_name_raw
    item.qty = body.qty
    item.unit_cost = body.unit_cost
    await db.commit()
    return await _load_invoice(db, invoice_id)


@router.delete(
    "/{invoice_id}/items/{item_id}",
    response_model=InvoiceOut,
    dependencies=[Depends(require_token)],
)
async def delete_item(invoice_id: int, item_id: int, db: AsyncSession = Depends(get_db)):
    item = await db.get(PurchaseInvoiceItem, item_id)
    if not item or item.purchase_invoice_id != invoice_id:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.product_id and item.qty:
        await reverse_stock_movement(
            db,
            product_id=item.product_id,
            qty_change=-item.qty,
            reference_id=invoice_id,
            reference_type="purchase_invoice_item_delete",
        )
    await db.delete(item)
    await db.commit()
    return await _load_invoice(db, invoice_id)


# ── OCR receipt upload ──────────────────────────────────────────────────────
#
# Used by the dashboard "Upload receipt" flow on the New-Invoice form.
# Saves the file, hands it to the same Claude Vision call the Telegram bot
# uses (`bot/services/ocr.py`), and returns the extracted fields for the user
# to confirm. Does NOT persist an invoice — the dashboard submits the regular
# `POST /invoices` once the user clicks Save.

def _import_ocr():
    """Import bot.services.ocr by inserting the bot/ directory on sys.path.
    Mirrors `src/bot/application.py` — same mechanism, kept narrowly scoped."""
    bot_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "bot")
    bot_dir = os.path.abspath(bot_dir)
    if os.path.exists(bot_dir) and bot_dir not in sys.path:
        sys.path.insert(0, bot_dir)
    from services.ocr import ocr_document  # noqa: WPS433 — deliberate lazy import
    return ocr_document


@router.post("/ocr", dependencies=[Depends(require_token)])
async def ocr_upload(file: UploadFile = File(...)):
    """Run OCR on an uploaded receipt and return extracted fields.
    No DB write — the dashboard renders the result in the invoice form for
    confirmation, then submits via the normal `POST /invoices` endpoint."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")

    ext = (file.filename.rsplit(".", 1)[-1] or "jpg").lower()
    if ext not in ("jpg", "jpeg", "png", "webp"):
        raise HTTPException(status_code=400, detail="Unsupported image format")

    images_dir = settings.images_dir
    os.makedirs(images_dir, exist_ok=True)
    local_path = os.path.join(images_dir, f"upload-{uuid.uuid4().hex}.{ext}")

    try:
        contents = await file.read()
        with open(local_path, "wb") as out:
            out.write(contents)

        # OCR (Claude Vision) — reuses the bot's prompt + retry wrapper.
        ocr_document = _import_ocr()
        extracted = ocr_document(local_path)

        # Optional R2 upload — image survives Render cold start when configured.
        image_path = local_path
        try:
            from services.storage import upload_image  # bot module, lazy-loaded above
            image_path = upload_image(local_path)
        except Exception as e:
            logger.warning("R2 upload skipped (%s) — keeping local path", e)

        extracted["image_path"] = image_path
        return extracted
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("OCR failed")
        raise HTTPException(status_code=500, detail=f"OCR failed: {e}")
    finally:
        # Clean up local file if it went to R2 successfully — `image_path`
        # changed only when R2 returned a URL (not the same local path).
        try:
            if "image_path" in locals() and image_path != local_path and os.path.exists(local_path):
                os.remove(local_path)
        except Exception:
            pass
