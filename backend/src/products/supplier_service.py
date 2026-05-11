"""
Supplier ledger aggregation — mirrors `customers/service.py`.

For a supplier, purchase invoices are debits (we owe them), outflow payments
against those invoices are credits (we paid them). The two are joined by
`payments.purchase_invoice_id`, so the ledger walks both tables and merges
chronologically.
"""
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.invoices.models import PurchaseInvoice
from src.payments.models import Payment
from src.products.models import Supplier


# ── Schemas live here (small + tightly coupled to the service) ──────────────

class SupplierUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    address: str | None = None


class SupplierSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    phone: str | None
    total_invoiced: Decimal
    total_paid: Decimal
    balance: Decimal           # positive = we owe the supplier
    last_activity: date | None


class SupplierLedgerEntry(BaseModel):
    entry_date: date
    entry_type: str            # "invoice" | "payment"
    description: str
    debit: Decimal             # invoice amount (we owe)
    credit: Decimal            # payment amount (we paid)
    running_balance: Decimal
    source_id: int


class SupplierLedger(BaseModel):
    supplier_id: int
    supplier_name: str
    phone: str | None
    address: str | None
    entries: list[SupplierLedgerEntry]
    total_invoiced: Decimal
    total_paid: Decimal
    balance: Decimal


def compute_supplier_ledger(
    supplier: Supplier,
    invoices: list[PurchaseInvoice],
    payments: list[Payment],
) -> SupplierLedger:
    """Pure function. Merges invoices (debits) and outflow payments (credits)
    chronologically and walks a running balance. Unit-testable without a DB."""
    entries: list[tuple] = []
    for inv in invoices:
        entries.append((inv.invoice_date, "invoice", inv.id, inv))
    for pay in payments:
        if pay.direction != "outflow":
            continue
        entries.append((pay.payment_date, "payment", pay.id, pay))
    entries.sort(key=lambda t: (t[0], t[1], t[2]))

    running = Decimal("0")
    total_invoiced = Decimal("0")
    total_paid = Decimal("0")
    out: list[SupplierLedgerEntry] = []
    for entry_date, kind, _id, obj in entries:
        if kind == "invoice":
            amount = obj.total_amount or Decimal("0")
            running += amount
            total_invoiced += amount
            out.append(SupplierLedgerEntry(
                entry_date=entry_date,
                entry_type="invoice",
                description=f"Invoice #{obj.invoice_number}",
                debit=amount,
                credit=Decimal("0"),
                running_balance=running,
                source_id=obj.id,
            ))
        else:
            amount = obj.amount or Decimal("0")
            running -= amount
            total_paid += amount
            out.append(SupplierLedgerEntry(
                entry_date=entry_date,
                entry_type="payment",
                description=f"{obj.payment_mode}" + (f" · ref {obj.transaction_ref}" if obj.transaction_ref else ""),
                debit=Decimal("0"),
                credit=amount,
                running_balance=running,
                source_id=obj.id,
            ))

    return SupplierLedger(
        supplier_id=supplier.id,
        supplier_name=supplier.name,
        phone=supplier.phone,
        address=supplier.address,
        entries=out,
        total_invoiced=total_invoiced,
        total_paid=total_paid,
        balance=running,
    )


async def build_supplier_ledger(db: AsyncSession, supplier: Supplier) -> SupplierLedger:
    invoices_res = await db.execute(
        select(PurchaseInvoice).where(PurchaseInvoice.supplier_id == supplier.id)
        .order_by(PurchaseInvoice.invoice_date, PurchaseInvoice.id)
    )
    invoices = list(invoices_res.scalars().all())
    invoice_ids = [inv.id for inv in invoices]

    if invoice_ids:
        payments_res = await db.execute(
            select(Payment)
            .where(Payment.purchase_invoice_id.in_(invoice_ids), Payment.direction == "outflow")
            .order_by(Payment.payment_date, Payment.id)
        )
        payments = list(payments_res.scalars().all())
    else:
        payments = []

    return compute_supplier_ledger(supplier, invoices, payments)


async def summarise_supplier(db: AsyncSession, supplier: Supplier) -> SupplierSummary:
    """Totals + last-activity date — cheaper than the full ledger."""
    invoices_res = await db.execute(
        select(PurchaseInvoice).where(PurchaseInvoice.supplier_id == supplier.id)
    )
    invoices = list(invoices_res.scalars().all())

    total_invoiced = Decimal("0")
    total_paid = Decimal("0")
    last_activity: date | None = None

    for inv in invoices:
        total_invoiced += inv.total_amount or Decimal("0")
        total_paid += inv.paid_amount or Decimal("0")
        if last_activity is None or inv.invoice_date > last_activity:
            last_activity = inv.invoice_date

    return SupplierSummary(
        id=supplier.id,
        name=supplier.name,
        phone=supplier.phone,
        total_invoiced=total_invoiced,
        total_paid=total_paid,
        balance=total_invoiced - total_paid,
        last_activity=last_activity,
    )
