from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class SupplierCreate(BaseModel):
    name: str
    phone: str | None = None
    address: str | None = None


class SupplierOut(SupplierCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class ProductCreate(BaseModel):
    sku: str
    barcode: str | None = None
    name: str
    unit: str | None = None
    cost_price: Decimal = Decimal("0")
    selling_price: Decimal = Decimal("0")
    stock_qty: Decimal = Decimal("0")
    reorder_level: Decimal = Decimal("0")
    supplier_id: int | None = None


class ProductUpdate(BaseModel):
    sku: str | None = None
    barcode: str | None = None
    name: str | None = None
    unit: str | None = None
    cost_price: Decimal | None = None
    selling_price: Decimal | None = None
    stock_qty: Decimal | None = None
    reorder_level: Decimal | None = None
    is_active: bool | None = None


class ProductOut(ProductCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_active: bool
    created_at: datetime
