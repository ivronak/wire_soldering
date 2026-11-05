"""lab qc: need-correction result and corrections list

Revision ID: d7a2b8c4e1f9
Revises: c6f1a9d3e8b2
Create Date: 2026-11-04 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd7a2b8c4e1f9'
down_revision = 'c6f1a9d3e8b2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('stage_lab_qc', schema=None) as batch_op:
        batch_op.alter_column('result', existing_type=sa.String(length=8), type_=sa.String(length=20), existing_nullable=False)
        batch_op.add_column(sa.Column('corrections', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('stage_lab_qc', schema=None) as batch_op:
        batch_op.drop_column('corrections')
        batch_op.alter_column('result', existing_type=sa.String(length=20), type_=sa.String(length=8), existing_nullable=False)
