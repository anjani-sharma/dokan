"""Payment business logic — shared between HTTP router and bulk-import worker."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.payments.models import Payment
from src.payments.schemas import PaymentCreate


async def create_payment(
    db: AsyncSession,
    body: PaymentCreate,
    *,
    content_fingerprint: str | None = None,
) -> Payment:
    """Create a payment and (legacy) bump the linked invoice's paid_amount."""
    payment = Payment(**body.model_dump(), content_fingerprint=content_fingerprint)
    db.add(payment)

    # Legacy: if the user explicitly tied the payment to one invoice (and not
    # a supplier), bump that invoice's paid_amount so the per-invoice "paid"
    # badge stays meaningful. Supplier-level payments leave individual invoices
    # alone — the supplier ledger is the source of truth for "what we owe".
    if (
        body.direction == "outflow"
        and body.purchase_invoice_id
        and not body.supplier_id
    ):
        from src.invoices.models import PurchaseInvoice
        invoice = await db.get(PurchaseInvoice, body.purchase_invoice_id)
        if invoice:
            invoice.paid_amount += body.amount
            if invoice.paid_amount >= invoice.total_amount:
                invoice.status = "paid"
            elif invoice.paid_amount > 0:
                invoice.status = "partial"

    await db.flush()
    return payment
