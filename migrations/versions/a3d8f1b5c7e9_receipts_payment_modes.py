"""sales S5: payment modes master (seeded), sales receipts and allocations

Revision ID: a3d8f1b5c7e9
Revises: f2c7e9a1b3d5
Create Date: 2026-11-19
"""
from alembic import op
import sqlalchemy as sa

revision = "a3d8f1b5c7e9"
down_revision = "f2c7e9a1b3d5"
branch_labels = None
depends_on = None


def upgrade():
    # Teen naye table; purane data par koi asar nahi. Payment modes me 4 shuruaati rows (master me baad me badal / jod sakte hain)
    modes = op.create_table(
        "payment_modes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.bulk_insert(modes, [
        {"id": 1, "code": "PM-0001", "name": "Cash", "is_active": True, "is_deleted": False},
        {"id": 2, "code": "PM-0002", "name": "Bank transfer", "is_active": True, "is_deleted": False},
        {"id": 3, "code": "PM-0003", "name": "UPI", "is_active": True, "is_deleted": False},
        {"id": 4, "code": "PM-0004", "name": "Cheque", "is_active": True, "is_deleted": False},
    ])
    op.create_table(
        "sales_receipts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("receipt_no", sa.String(20), nullable=False, unique=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("receipt_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("payment_mode_id", sa.Integer(), sa.ForeignKey("payment_modes.id"), nullable=False),
        sa.Column("reference", sa.String(60), nullable=True),
        sa.Column("notes", sa.String(255), nullable=True),
        sa.Column("status", sa.String(12), nullable=False, server_default="Posted"),
        sa.Column("cancel_reason", sa.String(255), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.create_table(
        "sales_receipt_allocations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("receipt_id", sa.Integer(), sa.ForeignKey("sales_receipts.id"), nullable=False),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("sales_invoices.id"), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
    )


def downgrade():
    op.drop_table("sales_receipt_allocations")
    op.drop_table("sales_receipts")
    op.drop_table("payment_modes")
