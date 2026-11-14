"""production orders: bundle_no (one party order with many products)

Revision ID: e3a7c9b1d5f8
Revises: d2f6b8a1c3e5
Create Date: 2026-11-14 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'e3a7c9b1d5f8'
down_revision = 'd2f6b8a1c3e5'
branch_labels = None
depends_on = None


def upgrade():
    # Purane orders ka bundle khaali (NULL) rehta hai — wo single orders hi hain.
    with op.batch_alter_table('production_orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('bundle_no', sa.String(length=20), nullable=True))
        batch_op.create_index(batch_op.f('ix_production_orders_bundle_no'), ['bundle_no'], unique=False)


def downgrade():
    with op.batch_alter_table('production_orders', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_production_orders_bundle_no'))
        batch_op.drop_column('bundle_no')
