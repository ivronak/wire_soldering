"""billet stage (ingot casting) + no-scrap stages

Revision ID: b5e8f2a1c4d6
Revises: a3d9c1e7b5f2
Create Date: 2026-11-04 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b5e8f2a1c4d6'
down_revision = 'a3d9c1e7b5f2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('work_stage', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_billet_stage', sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.add_column(sa.Column('billet_weight', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('no_scrap', sa.Boolean(), server_default=sa.false(), nullable=False))
    with op.batch_alter_table('production_order_stages', schema=None) as batch_op:
        batch_op.add_column(sa.Column('billet_count', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('billet_weight', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('scrap_photo', sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table('production_order_stages', schema=None) as batch_op:
        batch_op.drop_column('scrap_photo')
        batch_op.drop_column('billet_weight')
        batch_op.drop_column('billet_count')
    with op.batch_alter_table('work_stage', schema=None) as batch_op:
        batch_op.drop_column('no_scrap')
        batch_op.drop_column('billet_weight')
        batch_op.drop_column('is_billet_stage')
