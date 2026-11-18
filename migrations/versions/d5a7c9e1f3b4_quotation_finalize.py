"""sales S2: quotation finalize (customer PO no / date / copy, bundle) + quotation line -> production order link

Revision ID: d5a7c9e1f3b4
Revises: c4f6b8d0e2a3
Create Date: 2026-11-18
"""
from alembic import op
import sqlalchemy as sa

revision = "d5a7c9e1f3b4"
down_revision = "c4f6b8d0e2a3"
branch_labels = None
depends_on = None


def upgrade():
    # Sirf naye nullable columns (purani quotations par koi asar nahi)
    with op.batch_alter_table("quotations") as batch:
        batch.add_column(sa.Column("customer_po_no", sa.String(length=50), nullable=True))
        batch.add_column(sa.Column("customer_po_date", sa.Date(), nullable=True))
        batch.add_column(sa.Column("po_file", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("finalized_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("bundle_no", sa.String(length=20), nullable=True))
    with op.batch_alter_table("quotation_lines") as batch:
        batch.add_column(sa.Column("production_order_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_quotation_lines_production_order", "production_orders", ["production_order_id"], ["id"])


def downgrade():
    with op.batch_alter_table("quotation_lines") as batch:
        batch.drop_constraint("fk_quotation_lines_production_order", type_="foreignkey")
        batch.drop_column("production_order_id")
    with op.batch_alter_table("quotations") as batch:
        for name in ("bundle_no", "finalized_at", "po_file", "customer_po_date", "customer_po_no"):
            batch.drop_column(name)
