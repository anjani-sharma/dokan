"""customers table + customer_id FK on daily_sales and payments

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-11
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20)),
        sa.Column("address", sa.Text),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.add_column(
        "daily_sales",
        sa.Column("customer_id", sa.Integer, sa.ForeignKey("customers.id"), nullable=True),
    )
    op.create_index("ix_daily_sales_customer_id", "daily_sales", ["customer_id"])

    op.add_column(
        "payments",
        sa.Column("customer_id", sa.Integer, sa.ForeignKey("customers.id"), nullable=True),
    )
    op.create_index("ix_payments_customer_id", "payments", ["customer_id"])


def downgrade() -> None:
    op.drop_index("ix_payments_customer_id", "payments")
    op.drop_column("payments", "customer_id")
    op.drop_index("ix_daily_sales_customer_id", "daily_sales")
    op.drop_column("daily_sales", "customer_id")
    op.drop_table("customers")
