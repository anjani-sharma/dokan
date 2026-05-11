from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PaymentCreate(BaseModel):
    payment_date: date
    amount: Decimal
    payment_mode: str  # cash | bank_deposit | gpay | upi | other
    direction: str     # inflow | outflow
    purchase_invoice_id: int | None = None
    customer_id: int | None = None        # meaningful for inflows
    transaction_ref: str | None = None
    image_path: str | None = None
    note: str | None = None


class PaymentOut(PaymentCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    image_path: str | None
    created_at: datetime
