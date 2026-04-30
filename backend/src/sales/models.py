from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db import Base


class DailySale(Base):
    __tablename__ = "daily_sales"

    id: Mapped[int] = mapped_column(primary_key=True)
    sale_date: Mapped[date] = mapped_column(Date, nullable=False)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    product_name_raw: Mapped[str | None] = mapped_column(String(255))
    qty_sold: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    selling_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="voice")
    raw_input: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    product: Mapped["Product | None"] = relationship(back_populates="daily_sales")

    @property
    def line_total(self) -> Decimal:
        return self.qty_sold * self.selling_price


from src.products.models import Product  # noqa: E402
