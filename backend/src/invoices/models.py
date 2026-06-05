from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db import Base


class PurchaseInvoice(Base):
    __tablename__ = "purchase_invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"))
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(20), default="unpaid")
    image_path: Mapped[str | None] = mapped_column(Text)
    raw_ocr_text: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    image_phash: Mapped[str | None] = mapped_column(String(16), index=True)
    content_fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    supplier: Mapped["Supplier"] = relationship(back_populates="invoices")
    items: Mapped[list["PurchaseInvoiceItem"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )
    payments: Mapped[list["Payment"]] = relationship(back_populates="purchase_invoice")


class PurchaseInvoiceItem(Base):
    __tablename__ = "purchase_invoice_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_invoice_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_invoices.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    product_name_raw: Mapped[str | None] = mapped_column(String(255))
    qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    invoice: Mapped["PurchaseInvoice"] = relationship(back_populates="items")


from src.products.models import Supplier  # noqa: E402
from src.payments.models import Payment  # noqa: E402
