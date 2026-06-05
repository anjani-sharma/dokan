"""bulk import: import_jobs table, phash/fingerprint columns, suppliers.auto_created

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-27
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_jobs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("source_path", sa.Text, nullable=False),
        sa.Column("original_filename", sa.Text),
        sa.Column("mime_type", sa.String(64)),
        sa.Column("image_phash", sa.String(16)),
        sa.Column("content_fingerprint", sa.String(64)),
        sa.Column("extracted", sa.JSON),
        sa.Column("dup_of_invoice_id", sa.Integer, sa.ForeignKey("purchase_invoices.id")),
        sa.Column("dup_of_payment_id", sa.Integer, sa.ForeignKey("payments.id")),
        sa.Column("posted_invoice_id", sa.Integer, sa.ForeignKey("purchase_invoices.id")),
        sa.Column("posted_payment_id", sa.Integer, sa.ForeignKey("payments.id")),
        sa.Column("error", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_import_jobs_status", "import_jobs", ["status"])
    op.create_index("ix_import_jobs_image_phash", "import_jobs", ["image_phash"])
    op.create_index("ix_import_jobs_content_fingerprint", "import_jobs", ["content_fingerprint"])

    op.add_column("purchase_invoices", sa.Column("image_phash", sa.String(16)))
    op.add_column("purchase_invoices", sa.Column("content_fingerprint", sa.String(64)))
    op.create_index("ix_purchase_invoices_image_phash", "purchase_invoices", ["image_phash"])
    op.create_index("ix_purchase_invoices_content_fingerprint", "purchase_invoices", ["content_fingerprint"])

    op.add_column("payments", sa.Column("content_fingerprint", sa.String(64)))
    op.create_index("ix_payments_content_fingerprint", "payments", ["content_fingerprint"])

    op.add_column(
        "suppliers",
        sa.Column("auto_created", sa.Boolean, nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("suppliers", "auto_created")

    op.drop_index("ix_payments_content_fingerprint", "payments")
    op.drop_column("payments", "content_fingerprint")

    op.drop_index("ix_purchase_invoices_content_fingerprint", "purchase_invoices")
    op.drop_index("ix_purchase_invoices_image_phash", "purchase_invoices")
    op.drop_column("purchase_invoices", "content_fingerprint")
    op.drop_column("purchase_invoices", "image_phash")

    op.drop_index("ix_import_jobs_content_fingerprint", "import_jobs")
    op.drop_index("ix_import_jobs_image_phash", "import_jobs")
    op.drop_index("ix_import_jobs_status", "import_jobs")
    op.drop_table("import_jobs")
