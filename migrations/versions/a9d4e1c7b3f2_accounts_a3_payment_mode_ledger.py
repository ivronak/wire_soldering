"""accounts A3 - payment_modes.ledger_id (cash / bank ledger link)

Revision ID: a9d4e1c7b3f2
Revises: f8c2d5a1e9b6
Create Date: 2026-11-25 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'a9d4e1c7b3f2'
down_revision = 'f8c2d5a1e9b6'
branch_labels = None
depends_on = None

# Sirf ek nullable column ADD. Ledger pehli receipt par apne aap bante hain, isliye purana data nahi chhoota.


def upgrade():
    with op.batch_alter_table("payment_modes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("ledger_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_payment_modes_ledger", "ledgers", ["ledger_id"], ["id"])


def downgrade():
    with op.batch_alter_table("payment_modes", schema=None) as batch_op:
        batch_op.drop_constraint("fk_payment_modes_ledger", type_="foreignkey")
        batch_op.drop_column("ledger_id")
