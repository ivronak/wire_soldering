"""product min and max stock for finished goods alerts

Revision ID: c3a9f5d8e1b2
Revises: b7c41d2e9a10
Create Date: 2026-10-31 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3a9f5d8e1b2'
down_revision = 'b7c41d2e9a10'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.add_column(sa.Column('min_stock', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('max_stock', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.drop_column('max_stock')
        batch_op.drop_column('min_stock')
