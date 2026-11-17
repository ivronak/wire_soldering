"""work stage: counted in pieces (PCS) from this stage (C15)

Revision ID: b6d2f8a4c1e7
Revises: a5c1e7b3d9f2
Create Date: 2026-11-17
"""
from alembic import op
import sqlalchemy as sa

revision = 'b6d2f8a4c1e7'
down_revision = 'a5c1e7b3d9f2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('work_stage') as batch:
        batch.add_column(sa.Column('counts_pcs', sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade():
    with op.batch_alter_table('work_stage') as batch:
        batch.drop_column('counts_pcs')
