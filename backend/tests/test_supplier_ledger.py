"""
Unit tests for supplier ledger math. No DB.
"""
from datetime import date, datetime
from decimal import Decimal

from src.invoices.models import PurchaseInvoice
from src.payments.models import Payment
from src.products.models import Supplier
from src.products.supplier_service import compute_supplier_ledger


def _supplier() -> Supplier:
    s = Supplier()
    s.id = 1
    s.name = "Acme Wires"
    s.phone = None
    s.address = None
    s.created_at = datetime(2026, 5, 1)
    return s


def _invoice(id_: int, when: date, total: str, number: str = "INV-1") -> PurchaseInvoice:
    inv = PurchaseInvoice()
    inv.id = id_
    inv.invoice_number = number
    inv.supplier_id = 1
    inv.invoice_date = when
    inv.total_amount = Decimal(total)
    inv.paid_amount = Decimal("0")
    inv.status = "unpaid"
    inv.image_path = None
    inv.raw_ocr_text = None
    inv.notes = None
    inv.created_at = datetime.combine(when, datetime.min.time())
    return inv


def _payment(id_: int, when: date, amount: str, invoice_id: int | None, direction: str = "outflow") -> Payment:
    p = Payment()
    p.id = id_
    p.payment_date = when
    p.amount = Decimal(amount)
    p.payment_mode = "bank_deposit"
    p.direction = direction
    p.purchase_invoice_id = invoice_id
    p.customer_id = None
    p.transaction_ref = None
    p.image_path = None
    p.note = None
    p.created_at = datetime.combine(when, datetime.min.time())
    return p


def test_empty_supplier_ledger():
    led = compute_supplier_ledger(_supplier(), [], [])
    assert led.total_invoiced == Decimal("0")
    assert led.total_paid == Decimal("0")
    assert led.balance == Decimal("0")
    assert led.entries == []


def test_invoice_creates_debit():
    invoices = [_invoice(1, date(2026, 5, 5), "5000.00")]
    led = compute_supplier_ledger(_supplier(), invoices, [])
    assert led.balance == Decimal("5000.00")
    assert led.entries[0].entry_type == "invoice"
    assert led.entries[0].debit == Decimal("5000.00")


def test_partial_payment():
    invoices = [_invoice(1, date(2026, 5, 5), "5000.00")]
    payments = [_payment(1, date(2026, 5, 7), "2000.00", invoice_id=1)]
    led = compute_supplier_ledger(_supplier(), invoices, payments)
    assert led.total_invoiced == Decimal("5000.00")
    assert led.total_paid == Decimal("2000.00")
    assert led.balance == Decimal("3000.00")
    assert led.entries[1].running_balance == Decimal("3000.00")


def test_full_payment_clears_balance():
    invoices = [_invoice(1, date(2026, 5, 5), "1000.00")]
    payments = [_payment(1, date(2026, 5, 6), "1000.00", invoice_id=1)]
    led = compute_supplier_ledger(_supplier(), invoices, payments)
    assert led.balance == Decimal("0.00")


def test_inflow_payments_ignored():
    """A customer paying us isn't a supplier credit — must not appear in supplier ledger."""
    invoices = [_invoice(1, date(2026, 5, 5), "1000.00")]
    payments = [
        _payment(1, date(2026, 5, 6), "200.00", invoice_id=1, direction="outflow"),
        _payment(2, date(2026, 5, 6), "9999.00", invoice_id=None, direction="inflow"),  # not ours
    ]
    led = compute_supplier_ledger(_supplier(), invoices, payments)
    assert led.total_paid == Decimal("200.00")
    assert led.balance == Decimal("800.00")


def test_chronological_ordering():
    invoices = [
        _invoice(2, date(2026, 5, 10), "300.00", number="INV-B"),
        _invoice(1, date(2026, 5, 5),  "100.00", number="INV-A"),
    ]
    payments = [_payment(1, date(2026, 5, 7), "50.00", invoice_id=1)]
    led = compute_supplier_ledger(_supplier(), invoices, payments)
    dates = [e.entry_date for e in led.entries]
    assert dates == sorted(dates)
    assert [e.running_balance for e in led.entries] == [
        Decimal("100.00"), Decimal("50.00"), Decimal("350.00"),
    ]
