"""fix_list 13: dispatch line par maal ka source (own / free / borrowed) + udhaar ka reason

Revision ID: d6a1c8e2f4b3
Revises: c5f0b3d7e9a2
Create Date: 2026-11-20
"""
from alembic import op
import sqlalchemy as sa

revision = "d6a1c8e2f4b3"
down_revision = "c5f0b3d7e9a2"
branch_labels = None
depends_on = None


def upgrade():
    # Teen nayi columns; purani rows ka source from_own_order se nikalte hain (True = own, False = free)
    with op.batch_alter_table("delivery_challan_lines") as batch:
        batch.add_column(sa.Column("source_kind", sa.String(10), nullable=False, server_default="own"))
        batch.add_column(sa.Column("borrowed_from_quotation_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("borrow_reason", sa.String(255), nullable=True))
        batch.create_foreign_key("fk_dcl_borrowed_from_quotation", "quotations", ["borrowed_from_quotation_id"], ["id"])
    op.execute(sa.text("UPDATE delivery_challan_lines SET source_kind = 'free' WHERE from_own_order = 0"))


def downgrade():
    with op.batch_alter_table("delivery_challan_lines") as batch:
        batch.drop_constraint("fk_dcl_borrowed_from_quotation", type_="foreignkey")
        batch.drop_column("borrow_reason")
        batch.drop_column("borrowed_from_quotation_id")
        batch.drop_column("source_kind")
