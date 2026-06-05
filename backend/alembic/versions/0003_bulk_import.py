"""bulk import: import_jobs table, phash/fingerprint columns, suppliers.auto_created

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-27

Idempotent: each create_* check inspects the live schema first. The Render
deploy bootstrapped via SQLAlchemy create_all left `import_jobs` already
present but the column adds on existing tables (`suppliers.auto_created`
etc.) un-applied; skipping the table create lets the rest of the migration
finish on those DBs.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def _has_table(insp, name: str) -> bool:
    return name in insp.get_table_names()


def _has_column(insp, table: str, col: str) -> bool:
    return any(c["name"] == col for c in insp.get_columns(table))


def _has_index(insp, table: str, name: str) -> bool:
    return any(ix["name"] == name for ix in insp.get_indexes(table))


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    if not _has_table(insp, "import_jobs"):
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

    # Re-inspect after potential table create so index helpers see the table.
    insp = inspect(bind)
    if _has_table(insp, "import_jobs"):
        if not _has_index(insp, "import_jobs", "ix_import_jobs_status"):
            op.create_index("ix_import_jobs_status", "import_jobs", ["status"])
        if not _has_index(insp, "import_jobs", "ix_import_jobs_image_phash"):
            op.create_index("ix_import_jobs_image_phash", "import_jobs", ["image_phash"])
        if not _has_index(insp, "import_jobs", "ix_import_jobs_content_fingerprint"):
            op.create_index("ix_import_jobs_content_fingerprint", "import_jobs", ["content_fingerprint"])

    if not _has_column(insp, "purchase_invoices", "image_phash"):
        op.add_column("purchase_invoices", sa.Column("image_phash", sa.String(16)))
    if not _has_column(insp, "purchase_invoices", "content_fingerprint"):
        op.add_column("purchase_invoices", sa.Column("content_fingerprint", sa.String(64)))

    insp = inspect(bind)
    if not _has_index(insp, "purchase_invoices", "ix_purchase_invoices_image_phash"):
        op.create_index("ix_purchase_invoices_image_phash", "purchase_invoices", ["image_phash"])
    if not _has_index(insp, "purchase_invoices", "ix_purchase_invoices_content_fingerprint"):
        op.create_index("ix_purchase_invoices_content_fingerprint", "purchase_invoices", ["content_fingerprint"])

    if not _has_column(insp, "payments", "content_fingerprint"):
        op.add_column("payments", sa.Column("content_fingerprint", sa.String(64)))
    insp = inspect(bind)
    if not _has_index(insp, "payments", "ix_payments_content_fingerprint"):
        op.create_index("ix_payments_content_fingerprint", "payments", ["content_fingerprint"])

    if not _has_column(insp, "suppliers", "auto_created"):
        op.add_column(
            "suppliers",
            sa.Column("auto_created", sa.Boolean, nullable=False, server_default="false"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    if _has_column(insp, "suppliers", "auto_created"):
        op.drop_column("suppliers", "auto_created")

    if _has_index(insp, "payments", "ix_payments_content_fingerprint"):
        op.drop_index("ix_payments_content_fingerprint", "payments")
    if _has_column(insp, "payments", "content_fingerprint"):
        op.drop_column("payments", "content_fingerprint")

    if _has_index(insp, "purchase_invoices", "ix_purchase_invoices_content_fingerprint"):
        op.drop_index("ix_purchase_invoices_content_fingerprint", "purchase_invoices")
    if _has_index(insp, "purchase_invoices", "ix_purchase_invoices_image_phash"):
        op.drop_index("ix_purchase_invoices_image_phash", "purchase_invoices")
    if _has_column(insp, "purchase_invoices", "content_fingerprint"):
        op.drop_column("purchase_invoices", "content_fingerprint")
    if _has_column(insp, "purchase_invoices", "image_phash"):
        op.drop_column("purchase_invoices", "image_phash")

    if _has_table(insp, "import_jobs"):
        if _has_index(insp, "import_jobs", "ix_import_jobs_content_fingerprint"):
            op.drop_index("ix_import_jobs_content_fingerprint", "import_jobs")
        if _has_index(insp, "import_jobs", "ix_import_jobs_image_phash"):
            op.drop_index("ix_import_jobs_image_phash", "import_jobs")
        if _has_index(insp, "import_jobs", "ix_import_jobs_status"):
            op.drop_index("ix_import_jobs_status", "import_jobs")
        op.drop_table("import_jobs")
