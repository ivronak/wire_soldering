"""vendor lead time days

Revision ID: b9e4c2a7d1f3
Revises: a6d3b8c1e4f7
Create Date: 2026-10-31 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b9e4c2a7d1f3'
down_revision = 'a6d3b8c1e4f7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('vendors', schema=None) as batch_op:
        batch_op.add_column(sa.Column('lead_time_days', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('vendors', schema=None) as batch_op:
        batch_op.drop_column('lead_time_days')
