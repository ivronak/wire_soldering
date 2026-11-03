"""allowance percent per order line (moved from order)

Revision ID: d1f6b3a8c2e9
Revises: c7a2e5d9b1f4
Create Date: 2026-11-03 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd1f6b3a8c2e9'
down_revision = 'c7a2e5d9b1f4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('production_order_lines', schema=None) as batch_op:
        batch_op.add_column(sa.Column('allowance_percent', sa.Float(), server_default='0', nullable=False))
    # Pehle order-level % laga tha: use har line par copy karo, phir order ka column hata do
    op.execute("UPDATE production_order_lines SET allowance_percent = COALESCE((SELECT allowance_percent FROM production_orders WHERE production_orders.id = production_order_lines.production_order_id), 0)")
    with op.batch_alter_table('production_orders', schema=None) as batch_op:
        batch_op.drop_column('allowance_percent')


def downgrade():
    with op.batch_alter_table('production_orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('allowance_percent', sa.Float(), server_default='0', nullable=False))
    with op.batch_alter_table('production_order_lines', schema=None) as batch_op:
        batch_op.drop_column('allowance_percent')
