from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db import Base


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    payment_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    purchase_invoice_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_invoices.id"))
    transaction_ref: Mapped[str | None] = mapped_column(String(100))
    image_path: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    purchase_invoice: Mapped["PurchaseInvoice | None"] = relationship(back_populates="payments")


from src.invoices.models import PurchaseInvoice  # noqa: E402
