"""routing stage hold: held_at, hold_minutes, hold_reason

Revision ID: c1e5a7b9d204
Revises: b9d4f1a6c3e8
Create Date: 2026-11-13 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c1e5a7b9d204'
down_revision = 'b9d4f1a6c3e8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('production_order_stages', schema=None) as batch_op:
        batch_op.add_column(sa.Column('held_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('hold_reason', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('hold_minutes', sa.Float(), server_default='0', nullable=False))


def downgrade():
    with op.batch_alter_table('production_order_stages', schema=None) as batch_op:
        batch_op.drop_column('hold_minutes')
        batch_op.drop_column('hold_reason')
        batch_op.drop_column('held_at')
