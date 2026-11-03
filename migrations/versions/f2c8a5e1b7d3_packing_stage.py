"""packing item stage + order line kg_per_pack

Revision ID: f2c8a5e1b7d3
Revises: e4b7d2a9c6f1
Create Date: 2026-11-03 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f2c8a5e1b7d3'
down_revision = 'e4b7d2a9c6f1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('product_packing_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('work_stage_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_packing_item_stage', 'work_stage', ['work_stage_id'], ['id'])
    with op.batch_alter_table('production_order_lines', schema=None) as batch_op:
        batch_op.add_column(sa.Column('kg_per_pack', sa.Float(), nullable=True))


def downgrade():
    with op.batch_alter_table('production_order_lines', schema=None) as batch_op:
        batch_op.drop_column('kg_per_pack')
    with op.batch_alter_table('product_packing_items', schema=None) as batch_op:
        batch_op.drop_column('work_stage_id')
