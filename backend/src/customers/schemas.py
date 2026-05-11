from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class CustomerCreate(BaseModel):
    name: str
    phone: str | None = None
    address: str | None = None
    notes: str | None = None


class CustomerUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    address: str | None = None
    notes: str | None = None


class CustomerOut(CustomerCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class CustomerSummary(BaseModel):
    """Customer + running balance for list views."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    phone: str | None
    total_sales: Decimal
    total_received: Decimal
    balance: Decimal           # positive = customer owes us
    last_activity: date | None


class CustomerLedgerEntry(BaseModel):
    """One row in a customer's ledger — either a sale (debit) or inflow (credit)."""
    entry_date: date
    entry_type: str            # "sale" | "payment"
    description: str
    qty: Decimal | None = None
    debit: Decimal             # amount owed by customer (sales)
    credit: Decimal            # amount paid by customer (payments)
    running_balance: Decimal
    source_id: int


class CustomerLedger(BaseModel):
    customer: CustomerOut
    entries: list[CustomerLedgerEntry]
    total_sales: Decimal
    total_received: Decimal
    balance: Decimal
