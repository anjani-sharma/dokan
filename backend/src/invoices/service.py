"""Invoice business logic — single source of truth for creating a purchase invoice.

Both the HTTP router (`POST /invoices`) and the bulk-import worker call
`create_invoice` here. Keeping the body in one place means stock-movement
behavior, supplier-auto-upsert, and the 409 contract stay consistent.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.invoices.models import PurchaseInvoice, PurchaseInvoiceItem
from src.invoices.schemas import InvoiceCreate
from src.products.service import upsert_product_by_name
from src.stock.service import record_stock_movement


class DuplicateInvoiceNumber(Exception):
    """Raised when `invoice_number` collides with an existing row."""


async def create_invoice(
    db: AsyncSession,
    body: InvoiceCreate,
    *,
    image_phash: str | None = None,
    content_fingerprint: str | None = None,
) -> PurchaseInvoice:
    """Create an invoice, its items, and the matching stock movements.

    Raises `DuplicateInvoiceNumber` on `invoice_number` unique conflict.
    The router maps this to HTTP 409; the bot relies on the 409.
    """
    invoice = PurchaseInvoice(
        invoice_number=body.invoice_number,
        supplier_id=body.supplier_id,
        invoice_date=body.invoice_date,
        total_amount=body.total_amount,
        notes=body.notes,
        image_path=body.image_path,
        image_phash=image_phash,
        content_fingerprint=content_fingerprint,
    )
    db.add(invoice)
    # Savepoint isolates the unique-constraint check: if `invoice_number`
    # collides, only this savepoint rolls back. The caller's outer transaction
    # (e.g. the import worker's job-status writes) is preserved.
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError as e:
        raise DuplicateInvoiceNumber(body.invoice_number) from e

    for item_data in body.items:
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

    await db.flush()
    result = await db.execute(
        select(PurchaseInvoice)
        .options(selectinload(PurchaseInvoice.items))
        .where(PurchaseInvoice.id == invoice.id)
    )
    return result.scalar_one()
