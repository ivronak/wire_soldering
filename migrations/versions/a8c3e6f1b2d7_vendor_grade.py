"""vendor grade A/B/C

Revision ID: a8c3e6f1b2d7
Revises: d7a2b8c4e1f9
Create Date: 2026-11-13 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a8c3e6f1b2d7'
down_revision = 'd7a2b8c4e1f9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('vendors', schema=None) as batch_op:
        batch_op.add_column(sa.Column('grade', sa.String(length=1), nullable=True))


def downgrade():
    with op.batch_alter_table('vendors', schema=None) as batch_op:
        batch_op.drop_column('grade')
