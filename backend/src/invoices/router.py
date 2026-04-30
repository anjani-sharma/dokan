from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.dependencies import get_db
from src.invoices.models import PurchaseInvoice, PurchaseInvoiceItem
from src.invoices.schemas import InvoiceCreate, InvoiceOut, InvoiceUpdate
from src.stock.service import record_stock_movement

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


@router.post("", response_model=InvoiceOut, status_code=201)
async def create_invoice(body: InvoiceCreate, db: AsyncSession = Depends(get_db)):
    invoice = PurchaseInvoice(
        invoice_number=body.invoice_number,
        supplier_id=body.supplier_id,
        invoice_date=body.invoice_date,
        total_amount=body.total_amount,
        notes=body.notes,
    )
    db.add(invoice)
    await db.flush()  # get invoice.id before adding items

    for item_data in body.items:
        item = PurchaseInvoiceItem(purchase_invoice_id=invoice.id, **item_data.model_dump())
        db.add(item)
        if item_data.product_id:
            await record_stock_movement(
                db,
                product_id=item_data.product_id,
                movement_type="purchase",
                qty_change=item_data.qty,
                reference_id=invoice.id,
                reference_type="purchase_invoice",
            )

    await db.commit()
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


@router.put("/{invoice_id}", response_model=InvoiceOut)
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
