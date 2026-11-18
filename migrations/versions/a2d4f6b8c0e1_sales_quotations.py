"""sales S1: quotations + quotation lines

Revision ID: a2d4f6b8c0e1
Revises: f1b6d3e8a4c9
Create Date: 2026-11-18
"""
from alembic import op
import sqlalchemy as sa

revision = "a2d4f6b8c0e1"
down_revision = "f1b6d3e8a4c9"
branch_labels = None
depends_on = None


def upgrade():
    # Sirf naye tables — purane data ko haath nahi lagta
    op.create_table(
        "quotations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("quote_no", sa.String(20), nullable=False, unique=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("quote_date", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("needed_by_date", sa.Date(), nullable=True),
        sa.Column("payment_terms_id", sa.Integer(), sa.ForeignKey("payment_terms.id"), nullable=True),
        sa.Column("delivery_terms", sa.String(255), nullable=True),
        sa.Column("terms", sa.String(500), nullable=True),
        sa.Column("notes", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="Draft"),
        sa.Column("revision_no", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "quotation_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("quotation_id", sa.Integer(), sa.ForeignKey("quotations.id"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("qty", sa.Float(), nullable=False),
        sa.Column("rate", sa.Float(), nullable=False),
        sa.Column("discount_percent", sa.Float(), nullable=False, server_default="0"),
        sa.Column("tax_rate_id", sa.Integer(), sa.ForeignKey("tax_rates.id"), nullable=True),
        sa.Column("remarks", sa.String(150), nullable=True),
    )


def downgrade():
    op.drop_table("quotation_lines")
    op.drop_table("quotations")
