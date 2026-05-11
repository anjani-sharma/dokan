"""
Customer ledger aggregation.

Customers carry running balances: sales are debits (they owe us), inflow
payments are credits (they paid us). We compute the ledger by reading both
tables and merging chronologically.
"""
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.customers.models import Customer
from src.customers.schemas import (
    CustomerLedger, CustomerLedgerEntry, CustomerOut, CustomerSummary,
)
from src.payments.models import Payment
from src.sales.models import DailySale


def compute_ledger(
    customer: Customer,
    sales: list[DailySale],
    payments: list[Payment],
) -> CustomerLedger:
    """Pure function — merges sales (debits) and inflow payments (credits)
    chronologically and walks a running balance. Extracted from `build_ledger`
    so it can be unit-tested without a database."""
    entries: list[tuple] = []
    for s in sales:
        entries.append((s.sale_date, "sale", s.id, s))
    for p in payments:
        if p.direction != "inflow":
            continue
        entries.append((p.payment_date, "payment", p.id, p))
    entries.sort(key=lambda t: (t[0], t[1], t[2]))

    running = Decimal("0")
    total_sales = Decimal("0")
    total_received = Decimal("0")
    out: list[CustomerLedgerEntry] = []
    for entry_date, kind, _id, obj in entries:
        if kind == "sale":
            amount = (obj.qty_sold or Decimal("0")) * (obj.selling_price or Decimal("0"))
            running += amount
            total_sales += amount
            out.append(CustomerLedgerEntry(
                entry_date=entry_date,
                entry_type="sale",
                description=obj.product_name_raw or "Sale",
                qty=obj.qty_sold,
                debit=amount,
                credit=Decimal("0"),
                running_balance=running,
                source_id=obj.id,
            ))
        else:
            amount = obj.amount or Decimal("0")
            running -= amount
            total_received += amount
            out.append(CustomerLedgerEntry(
                entry_date=entry_date,
                entry_type="payment",
                description=f"{obj.payment_mode}" + (f" · ref {obj.transaction_ref}" if obj.transaction_ref else ""),
                qty=None,
                debit=Decimal("0"),
                credit=amount,
                running_balance=running,
                source_id=obj.id,
            ))

    return CustomerLedger(
        customer=CustomerOut.model_validate(customer),
        entries=out,
        total_sales=total_sales,
        total_received=total_received,
        balance=running,
    )


async def build_ledger(db: AsyncSession, customer: Customer) -> CustomerLedger:
    sales_res = await db.execute(
        select(DailySale).where(DailySale.customer_id == customer.id).order_by(DailySale.sale_date, DailySale.id)
    )
    payments_res = await db.execute(
        select(Payment)
        .where(Payment.customer_id == customer.id, Payment.direction == "inflow")
        .order_by(Payment.payment_date, Payment.id)
    )
    return compute_ledger(
        customer,
        list(sales_res.scalars().all()),
        list(payments_res.scalars().all()),
    )


async def summarise_customer(db: AsyncSession, customer: Customer) -> CustomerSummary:
    """Cheaper than the full ledger — only totals + last-activity date."""
    sales = await db.execute(
        select(DailySale).where(DailySale.customer_id == customer.id)
    )
    payments = await db.execute(
        select(Payment).where(Payment.customer_id == customer.id, Payment.direction == "inflow")
    )

    total_sales = Decimal("0")
    last_activity = None
    for s in sales.scalars().all():
        total_sales += (s.qty_sold or Decimal("0")) * (s.selling_price or Decimal("0"))
        if last_activity is None or s.sale_date > last_activity:
            last_activity = s.sale_date

    total_received = Decimal("0")
    for p in payments.scalars().all():
        total_received += p.amount or Decimal("0")
        if last_activity is None or p.payment_date > last_activity:
            last_activity = p.payment_date

    return CustomerSummary(
        id=customer.id,
        name=customer.name,
        phone=customer.phone,
        total_sales=total_sales,
        total_received=total_received,
        balance=total_sales - total_received,
        last_activity=last_activity,
    )
