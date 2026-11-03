"""product category icon

Revision ID: e4b7d2a9c6f1
Revises: d1f6b3a8c2e9
Create Date: 2026-11-03 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'e4b7d2a9c6f1'
down_revision = 'd1f6b3a8c2e9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('product_categories', schema=None) as batch_op:
        batch_op.add_column(sa.Column('icon', sa.String(length=30), nullable=True))


def downgrade():
    with op.batch_alter_table('product_categories', schema=None) as batch_op:
        batch_op.drop_column('icon')
