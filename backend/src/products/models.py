from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    address: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    products: Mapped[list["Product"]] = relationship(back_populates="supplier")
    invoices: Mapped[list["PurchaseInvoice"]] = relationship(back_populates="supplier")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    # Optional UPC/EAN scanned at the till. Nullable because most legacy
    # products have no barcode and we don't want to block creation.
    barcode: Mapped[str | None] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(50))
    cost_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    selling_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    stock_qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=Decimal("0"))
    reorder_level: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("0"))
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    supplier: Mapped["Supplier | None"] = relationship(back_populates="products")
    stock_movements: Mapped[list["StockMovement"]] = relationship(back_populates="product")
    daily_sales: Mapped[list["DailySale"]] = relationship(back_populates="product")


# Imported here to avoid circular imports in relationship declarations
from src.invoices.models import PurchaseInvoice  # noqa: E402
from src.stock.models import StockMovement  # noqa: E402
from src.sales.models import DailySale  # noqa: E402
