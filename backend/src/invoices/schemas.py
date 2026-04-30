from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class InvoiceItemCreate(BaseModel):
    product_id: int | None = None
    product_name_raw: str | None = None
    qty: Decimal
    unit_cost: Decimal


class InvoiceItemOut(InvoiceItemCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    purchase_invoice_id: int


class InvoiceCreate(BaseModel):
    invoice_number: str
    supplier_id: int
    invoice_date: date
    total_amount: Decimal
    notes: str | None = None
    image_path: str | None = None
    items: list[InvoiceItemCreate] = []


class InvoiceUpdate(BaseModel):
    paid_amount: Decimal | None = None
    status: str | None = None
    notes: str | None = None


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    invoice_number: str
    supplier_id: int
    invoice_date: date
    total_amount: Decimal
    paid_amount: Decimal
    status: str
    image_path: str | None
    notes: str | None
    created_at: datetime
    items: list[InvoiceItemOut] = []
