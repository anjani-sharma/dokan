"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20)),
        sa.Column("address", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "products",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("sku", sa.String(100), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("unit", sa.String(50)),
        sa.Column("cost_price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("selling_price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("stock_qty", sa.Numeric(12, 3), nullable=False, server_default="0"),
        sa.Column("reorder_level", sa.Numeric(12, 3), server_default="0"),
        sa.Column("supplier_id", sa.Integer, sa.ForeignKey("suppliers.id")),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "purchase_invoices",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("invoice_number", sa.String(100), unique=True, nullable=False),
        sa.Column("supplier_id", sa.Integer, sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("invoice_date", sa.Date, nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("paid_amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("status", sa.String(20), server_default="unpaid"),
        sa.Column("image_path", sa.Text),
        sa.Column("raw_ocr_text", sa.Text),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "purchase_invoice_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("purchase_invoice_id", sa.Integer,
                  sa.ForeignKey("purchase_invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id")),
        sa.Column("product_name_raw", sa.String(255)),
        sa.Column("qty", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(12, 2), nullable=False),
    )

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("payment_date", sa.Date, nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("payment_mode", sa.String(20), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("purchase_invoice_id", sa.Integer, sa.ForeignKey("purchase_invoices.id")),
        sa.Column("transaction_ref", sa.String(100)),
        sa.Column("image_path", sa.Text),
        sa.Column("note", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "daily_sales",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("sale_date", sa.Date, nullable=False),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id")),
        sa.Column("product_name_raw", sa.String(255)),
        sa.Column("qty_sold", sa.Numeric(12, 3), nullable=False),
        sa.Column("selling_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("source", sa.String(20), server_default="voice"),
        sa.Column("raw_input", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "stock_movements",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id"), nullable=False),
        sa.Column("movement_type", sa.String(30), nullable=False),
        sa.Column("qty_change", sa.Numeric(12, 3), nullable=False),
        sa.Column("reference_id", sa.Integer),
        sa.Column("reference_type", sa.String(30)),
        sa.Column("note", sa.Text),
        sa.Column("moved_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("stock_movements")
    op.drop_table("daily_sales")
    op.drop_table("payments")
    op.drop_table("purchase_invoice_items")
    op.drop_table("purchase_invoices")
    op.drop_table("products")
    op.drop_table("suppliers")
