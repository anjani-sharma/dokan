from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class SaleCreate(BaseModel):
    sale_date: date
    product_id: int | None = None
    customer_id: int | None = None
    product_name_raw: str | None = None
    qty_sold: Decimal
    selling_price: Decimal
    source: str = "voice"
    raw_input: str | None = None
    # Optional point-of-sale payment captured alongside the sale.
    # When set, a matching inflow Payment row is created in the same
    # transaction so the cash drawer and the customer ledger update
    # immediately. Amount may be partial (less than qty * selling_price).
    payment_amount: Decimal | None = None
    payment_mode: str | None = None  # cash | gpay | upi | bank_deposit | other


class SaleUpdate(BaseModel):
    qty_sold: Decimal | None = None
    selling_price: Decimal | None = None
    product_id: int | None = None
    customer_id: int | None = None
    product_name_raw: str | None = None


class SaleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sale_date: date
    product_id: int | None
    customer_id: int | None
    product_name_raw: str | None
    qty_sold: Decimal
    selling_price: Decimal
    line_total: Decimal
    source: str
    created_at: datetime
