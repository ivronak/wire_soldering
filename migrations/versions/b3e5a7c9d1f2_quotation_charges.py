"""sales S1: quotation charges (Shipping, Labour ... from Charges Master)

Revision ID: b3e5a7c9d1f2
Revises: a2d4f6b8c0e1
Create Date: 2026-11-18
"""
from alembic import op
import sqlalchemy as sa

revision = "b3e5a7c9d1f2"
down_revision = "a2d4f6b8c0e1"
branch_labels = None
depends_on = None


def upgrade():
    # Sirf naya table — purana data waisa hi
    op.create_table(
        "quotation_charges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("quotation_id", sa.Integer(), sa.ForeignKey("quotations.id"), nullable=False),
        sa.Column("charge_id", sa.Integer(), sa.ForeignKey("charges.id"), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("effect", sa.String(10), nullable=False),
    )


def downgrade():
    op.drop_table("quotation_charges")
