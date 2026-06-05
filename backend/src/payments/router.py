from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dependencies import get_db, require_token
from src.payments.models import Payment
from src.payments.schemas import PaymentCreate, PaymentOut
from src.payments.service import create_payment as create_payment_service

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


@router.post("", response_model=PaymentOut, status_code=201, dependencies=[Depends(require_token)])
async def create_payment(body: PaymentCreate, db: AsyncSession = Depends(get_db)):
    payment = await create_payment_service(db, body)
    await db.commit()
    return payment


@router.get("/{payment_id}", response_model=PaymentOut)
async def get_payment(payment_id: int, db: AsyncSession = Depends(get_db)):
    payment = await db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment
