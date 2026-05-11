"""
Unit tests for the customer ledger math. No DB.

The DB-touching route tests would need a real Postgres (NUMERIC + GENERATED
columns rule from `.claude/rules/database.md`), so we test the pure
`compute_ledger` function instead and trust SQLAlchemy + the simple route code
to wire it up correctly.
"""
from datetime import date, datetime
from decimal import Decimal

from src.customers.models import Customer
from src.customers.service import compute_ledger
from src.payments.models import Payment
from src.sales.models import DailySale


def _customer() -> Customer:
    c = Customer()
    c.id = 1
    c.name = "Ravi"
    c.phone = None
    c.address = None
    c.notes = None
    c.created_at = datetime(2026, 5, 1)
    return c


def _sale(id_: int, when: date, qty: str, price: str, name: str = "MCB") -> DailySale:
    s = DailySale()
    s.id = id_
    s.sale_date = when
    s.product_id = None
    s.customer_id = 1
    s.product_name_raw = name
    s.qty_sold = Decimal(qty)
    s.selling_price = Decimal(price)
    s.source = "manual"
    s.raw_input = None
    s.created_at = datetime.combine(when, datetime.min.time())
    return s


def _payment(id_: int, when: date, amount: str, direction: str = "inflow") -> Payment:
    p = Payment()
    p.id = id_
    p.payment_date = when
    p.amount = Decimal(amount)
    p.payment_mode = "upi"
    p.direction = direction
    p.purchase_invoice_id = None
    p.customer_id = 1
    p.transaction_ref = None
    p.image_path = None
    p.note = None
    p.created_at = datetime.combine(when, datetime.min.time())
    return p


def test_empty_ledger_is_zero():
    ledger = compute_ledger(_customer(), [], [])
    assert ledger.balance == Decimal("0")
    assert ledger.total_sales == Decimal("0")
    assert ledger.total_received == Decimal("0")
    assert ledger.entries == []


def test_single_sale_creates_debit():
    sales = [_sale(1, date(2026, 5, 5), "2", "100.00")]
    ledger = compute_ledger(_customer(), sales, [])
    assert ledger.total_sales == Decimal("200.00")
    assert ledger.balance == Decimal("200.00")
    assert len(ledger.entries) == 1
    assert ledger.entries[0].debit == Decimal("200.00")
    assert ledger.entries[0].running_balance == Decimal("200.00")


def test_sale_then_partial_payment():
    sales = [_sale(1, date(2026, 5, 5), "2", "2500.00")]   # ₹5000 owed
    payments = [_payment(1, date(2026, 5, 7), "3000.00")]
    ledger = compute_ledger(_customer(), sales, payments)
    assert ledger.total_sales == Decimal("5000.00")
    assert ledger.total_received == Decimal("3000.00")
    assert ledger.balance == Decimal("2000.00")
    assert ledger.entries[0].running_balance == Decimal("5000.00")
    assert ledger.entries[1].running_balance == Decimal("2000.00")


def test_full_payment_clears_balance():
    sales = [_sale(1, date(2026, 5, 5), "1", "1000.00")]
    payments = [_payment(1, date(2026, 5, 6), "1000.00")]
    ledger = compute_ledger(_customer(), sales, payments)
    assert ledger.balance == Decimal("0.00")


def test_payment_before_sale_is_negative_balance():
    """Customer pays a deposit before any sale — they're in credit."""
    sales: list[DailySale] = []
    payments = [_payment(1, date(2026, 5, 1), "500.00")]
    ledger = compute_ledger(_customer(), sales, payments)
    assert ledger.balance == Decimal("-500.00")


def test_chronological_ordering():
    """Entries with mixed dates should sort by date even if added in any order."""
    sales = [
        _sale(2, date(2026, 5, 10), "1", "300.00"),
        _sale(1, date(2026, 5, 5), "1", "100.00"),
    ]
    payments = [_payment(1, date(2026, 5, 7), "50.00")]
    ledger = compute_ledger(_customer(), sales, payments)
    dates = [e.entry_date for e in ledger.entries]
    assert dates == sorted(dates)
    # Running balance walks: +100 → -50 → +300 = 350
    assert [e.running_balance for e in ledger.entries] == [
        Decimal("100.00"), Decimal("50.00"), Decimal("350.00"),
    ]


def test_outflow_payments_ignored():
    """Only inflow payments count — outflows (paying suppliers) are unrelated to customer ledger."""
    sales = [_sale(1, date(2026, 5, 5), "1", "1000.00")]
    payments = [
        _payment(1, date(2026, 5, 6), "300.00", direction="inflow"),
        _payment(2, date(2026, 5, 7), "9999.00", direction="outflow"),  # ignored
    ]
    ledger = compute_ledger(_customer(), sales, payments)
    assert ledger.total_received == Decimal("300.00")
    assert ledger.balance == Decimal("700.00")
