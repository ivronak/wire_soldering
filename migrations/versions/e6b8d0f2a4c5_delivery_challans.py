"""sales S3: delivery challans (dispatch) + challan lines

Revision ID: e6b8d0f2a4c5
Revises: d5a7c9e1f3b4
Create Date: 2026-11-18
"""
from alembic import op
import sqlalchemy as sa

revision = "e6b8d0f2a4c5"
down_revision = "d5a7c9e1f3b4"
branch_labels = None
depends_on = None


def upgrade():
    # Sirf do naye table (purane data par koi asar nahi)
    op.create_table(
        "delivery_challans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("challan_no", sa.String(20), nullable=False, unique=True),
        sa.Column("quotation_id", sa.Integer(), sa.ForeignKey("quotations.id"), nullable=False),
        sa.Column("challan_date", sa.Date(), nullable=False),
        sa.Column("transporter", sa.String(100), nullable=True),
        sa.Column("vehicle_no", sa.String(20), nullable=True),
        sa.Column("notes", sa.String(255), nullable=True),
        sa.Column("status", sa.String(12), nullable=False, server_default="Dispatched"),
        sa.Column("cancel_reason", sa.String(255), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.create_table(
        "delivery_challan_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("challan_id", sa.Integer(), sa.ForeignKey("delivery_challans.id"), nullable=False),
        sa.Column("quotation_line_id", sa.Integer(), sa.ForeignKey("quotation_lines.id"), nullable=False),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("fg_batches.id"), nullable=False),
        sa.Column("qty", sa.Float(), nullable=False),
        sa.Column("unit_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("from_own_order", sa.Boolean(), nullable=False, server_default="1"),
    )


def downgrade():
    op.drop_table("delivery_challan_lines")
    op.drop_table("delivery_challans")
