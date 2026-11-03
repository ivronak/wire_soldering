"""allowance percent on order, RM used on order line, work hours on stage

Revision ID: c7a2e5d9b1f4
Revises: b9e4c2a7d1f3
Create Date: 2026-11-02 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c7a2e5d9b1f4'
down_revision = 'b9e4c2a7d1f3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('production_orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('allowance_percent', sa.Float(), server_default='0', nullable=False))
    with op.batch_alter_table('production_order_lines', schema=None) as batch_op:
        batch_op.add_column(sa.Column('used_qty', sa.Float(), nullable=True))
    with op.batch_alter_table('production_order_stages', schema=None) as batch_op:
        batch_op.add_column(sa.Column('work_hours', sa.Float(), nullable=True))


def downgrade():
    with op.batch_alter_table('production_order_stages', schema=None) as batch_op:
        batch_op.drop_column('work_hours')
    with op.batch_alter_table('production_order_lines', schema=None) as batch_op:
        batch_op.drop_column('used_qty')
    with op.batch_alter_table('production_orders', schema=None) as batch_op:
        batch_op.drop_column('allowance_percent')
