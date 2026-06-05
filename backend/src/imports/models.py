from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


class ImportJob(Base):
    """One row per uploaded file in a bulk-import batch.

    Status flow: pending → extracting → (needs_review | duplicate) → posted | failed
    """

    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # "invoice" | "payment"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)

    source_path: Mapped[str] = mapped_column(Text, nullable=False)  # local path or R2 URL
    original_filename: Mapped[str | None] = mapped_column(Text)
    mime_type: Mapped[str | None] = mapped_column(String(64))

    image_phash: Mapped[str | None] = mapped_column(String(16), index=True)
    content_fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)

    extracted: Mapped[dict | None] = mapped_column(JSON)

    dup_of_invoice_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_invoices.id"))
    dup_of_payment_id: Mapped[int | None] = mapped_column(ForeignKey("payments.id"))
    posted_invoice_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_invoices.id"))
    posted_payment_id: Mapped[int | None] = mapped_column(ForeignKey("payments.id"))

    error: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
