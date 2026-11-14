"""production orders: plan_confirmed (Production planning step before Release)

Revision ID: d2f6b8a1c3e5
Revises: c1e5a7b9d204
Create Date: 2026-11-14 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd2f6b8a1c3e5'
down_revision = 'c1e5a7b9d204'
branch_labels = None
depends_on = None


def upgrade():
    # Purane saare orders pehle se planned maane jaate hain (server_default 1), isliye koi Draft order Release se atakta nahi.
    with op.batch_alter_table('production_orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('plan_confirmed', sa.Boolean(), server_default='1', nullable=False))


def downgrade():
    with op.batch_alter_table('production_orders', schema=None) as batch_op:
        batch_op.drop_column('plan_confirmed')
