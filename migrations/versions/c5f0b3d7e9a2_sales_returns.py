"""sales S7: sales returns (credit notes) and their lines

Revision ID: c5f0b3d7e9a2
Revises: b4e9a2c6d8f1
Create Date: 2026-11-19
"""
from alembic import op
import sqlalchemy as sa

revision = "c5f0b3d7e9a2"
down_revision = "b4e9a2c6d8f1"
branch_labels = None
depends_on = None


def upgrade():
    # Do naye table; purane data par koi asar nahi
    op.create_table(
        "sales_returns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("return_no", sa.String(20), nullable=False, unique=True),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("sales_invoices.id"), nullable=False),
        sa.Column("return_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="Posted"),
        sa.Column("subtotal", sa.Float(), nullable=False, server_default="0"),
        sa.Column("tax_total", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("cancel_reason", sa.String(255), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.create_table(
        "sales_return_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("return_id", sa.Integer(), sa.ForeignKey("sales_returns.id"), nullable=False),
        sa.Column("invoice_line_id", sa.Integer(), sa.ForeignKey("sales_invoice_lines.id"), nullable=False),
        sa.Column("challan_line_id", sa.Integer(), sa.ForeignKey("delivery_challan_lines.id"), nullable=False),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("fg_batches.id"), nullable=False),
        sa.Column("qty", sa.Float(), nullable=False),
        sa.Column("good_qty", sa.Float(), nullable=False, server_default="0"),
    )


def downgrade():
    op.drop_table("sales_return_lines")
    op.drop_table("sales_returns")
