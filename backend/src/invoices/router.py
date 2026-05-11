import logging
import os
import sys
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.dependencies import get_db, require_token
from src.invoices.models import PurchaseInvoice, PurchaseInvoiceItem
from src.invoices.schemas import InvoiceCreate, InvoiceOut, InvoiceUpdate
from src.products.service import upsert_product_by_name
from src.settings import settings
from src.stock.service import record_stock_movement

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


@router.post("", response_model=InvoiceOut, status_code=201, dependencies=[Depends(require_token)])
async def create_invoice(body: InvoiceCreate, db: AsyncSession = Depends(get_db)):
    invoice = PurchaseInvoice(
        invoice_number=body.invoice_number,
        supplier_id=body.supplier_id,
        invoice_date=body.invoice_date,
        total_amount=body.total_amount,
        notes=body.notes,
        image_path=body.image_path,
    )
    db.add(invoice)
    await db.flush()  # get invoice.id before adding items

    for item_data in body.items:
        # If the caller didn't supply a product_id (typical for OCR'd line
        # items and bot-extracted ones), upsert a placeholder product by
        # name so the stock movement is recorded against a real row.
        product_id = item_data.product_id
        if not product_id and item_data.product_name_raw:
            product = await upsert_product_by_name(
                db,
                item_data.product_name_raw,
                default_cost=item_data.unit_cost,
            )
            if product:
                product_id = product.id

        item = PurchaseInvoiceItem(
            purchase_invoice_id=invoice.id,
            **{**item_data.model_dump(), "product_id": product_id},
        )
        db.add(item)
        if product_id:
            await record_stock_movement(
                db,
                product_id=product_id,
                movement_type="purchase",
                qty_change=item_data.qty,
                reference_id=invoice.id,
                reference_type="purchase_invoice",
            )

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail=f"Invoice {body.invoice_number} already exists")
    await db.refresh(invoice)
    result = await db.execute(
        select(PurchaseInvoice)
        .options(selectinload(PurchaseInvoice.items))
        .where(PurchaseInvoice.id == invoice.id)
    )
    return result.scalar_one()


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
    await db.refresh(invoice)
    return invoice


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
