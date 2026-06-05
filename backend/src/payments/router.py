from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.dependencies import get_db, require_token
from src.imports.models import ImportJob
from src.payments.models import Payment
from src.payments.schemas import PaymentCreate, PaymentOut
from src.payments.service import create_payment as create_payment_service


def _payment_dup_key(p: Payment) -> tuple:
    """Same shape compute_payment_fingerprint uses: date, ₹-rounded amount,
    lower-cased mode, stripped transaction ref. Plus supplier_id/customer_id
    so a deposit posted against two different vendors doesn't collapse."""
    return (
        p.payment_date.isoformat(),
        round(float(p.amount), 2),
        (p.payment_mode or "").lower(),
        (p.transaction_ref or "").strip(),
        p.direction,
        p.supplier_id,
        p.customer_id,
    )

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


@router.get("/duplicates", response_model=list[list[PaymentOut]])
async def find_duplicate_payments(db: AsyncSession = Depends(get_db)):
    """Group existing payments by (party, date, amount, mode, ref) and
    return clusters > 1 — the same key the bulk-import worker uses to
    detect duplicates at upload time, applied retroactively."""
    result = await db.execute(select(Payment).order_by(Payment.payment_date.desc()))
    payments = list(result.scalars().all())

    buckets: dict[tuple, list[Payment]] = {}
    for p in payments:
        buckets.setdefault(_payment_dup_key(p), []).append(p)

    return [group for group in buckets.values() if len(group) > 1]


@router.get("/{payment_id}", response_model=PaymentOut)
async def get_payment(payment_id: int, db: AsyncSession = Depends(get_db)):
    payment = await db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment


@router.delete("/{payment_id}", status_code=204, dependencies=[Depends(require_token)])
async def delete_payment(payment_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a payment. If the payment was tied to a specific invoice, the
    invoice's paid_amount is rolled back so the per-invoice paid status stays
    correct. Supplier-level outflows leave the supplier ledger to recompute
    on its own.
    """
    payment = await db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if (
        payment.direction == "outflow"
        and payment.purchase_invoice_id
        and not payment.supplier_id
    ):
        from src.invoices.models import PurchaseInvoice
        invoice = await db.get(PurchaseInvoice, payment.purchase_invoice_id)
        if invoice is not None:
            invoice.paid_amount -= payment.amount
            if invoice.paid_amount <= 0:
                invoice.paid_amount = 0  # type: ignore[assignment]
                invoice.status = "unpaid"
            elif invoice.paid_amount < invoice.total_amount:
                invoice.status = "partial"

    # Clear import_jobs FKs pointing at this payment so the delete isn't
    # blocked by the dup/posted references the bulk-import worker writes.
    await db.execute(
        update(ImportJob)
        .where(ImportJob.dup_of_payment_id == payment_id)
        .values(dup_of_payment_id=None)
    )
    await db.execute(
        update(ImportJob)
        .where(ImportJob.posted_payment_id == payment_id)
        .values(posted_payment_id=None)
    )
    await db.delete(payment)
    await db.commit()
