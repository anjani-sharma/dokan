from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dependencies import get_db
from src.payments.models import Payment
from src.payments.schemas import PaymentCreate, PaymentOut

router = APIRouter()


@router.get("", response_model=list[PaymentOut])
async def list_payments(
    payment_date: date | None = None,
    direction: str | None = None,
    payment_mode: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Payment).order_by(Payment.payment_date.desc())
    if payment_date:
        q = q.where(Payment.payment_date == payment_date)
    if direction:
        q = q.where(Payment.direction == direction)
    if payment_mode:
        q = q.where(Payment.payment_mode == payment_mode)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("", response_model=PaymentOut, status_code=201)
async def create_payment(body: PaymentCreate, db: AsyncSession = Depends(get_db)):
    payment = Payment(**body.model_dump())
    db.add(payment)

    # Update invoice paid_amount + status if linked
    if body.purchase_invoice_id and body.direction == "outflow":
        from src.invoices.models import PurchaseInvoice
        invoice = await db.get(PurchaseInvoice, body.purchase_invoice_id)
        if invoice:
            invoice.paid_amount += body.amount
            if invoice.paid_amount >= invoice.total_amount:
                invoice.status = "paid"
            elif invoice.paid_amount > 0:
                invoice.status = "partial"

    await db.commit()
    await db.refresh(payment)
    return payment


@router.get("/{payment_id}", response_model=PaymentOut)
async def get_payment(payment_id: int, db: AsyncSession = Depends(get_db)):
    payment = await db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment
