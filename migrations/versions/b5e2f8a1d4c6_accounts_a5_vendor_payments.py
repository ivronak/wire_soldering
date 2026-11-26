"""accounts A5 - vendor_payments + vendor_payment_allocations

Revision ID: b5e2f8a1d4c6
Revises: a9d4e1c7b3f2
Create Date: 2026-11-25 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'b5e2f8a1d4c6'
down_revision = 'a9d4e1c7b3f2'
branch_labels = None
depends_on = None

# Sirf 2 naye tables (add-only). Purane data ko nahi chhoota.


def upgrade():
    op.create_table(
        "vendor_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("payment_no", sa.String(20), nullable=False, unique=True),
        sa.Column("vendor_id", sa.Integer(), sa.ForeignKey("vendors.id"), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("payment_mode_id", sa.Integer(), sa.ForeignKey("payment_modes.id"), nullable=False),
        sa.Column("reference", sa.String(60), nullable=True),
        sa.Column("notes", sa.String(255), nullable=True),
        sa.Column("status", sa.String(12), nullable=False, server_default="Posted"),
        sa.Column("cancel_reason", sa.String(255), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("cancelled_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "vendor_payment_allocations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("vendor_payments.id"), nullable=False),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("purchase_invoices.id"), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table("vendor_payment_allocations")
    op.drop_table("vendor_payments")
