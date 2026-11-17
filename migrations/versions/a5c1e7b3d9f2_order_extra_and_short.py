"""production order: extra % for scrap (C18) + short-qty decision + balance order link

Revision ID: a5c1e7b3d9f2
Revises: f4b8d0c2e6a9
Create Date: 2026-11-17
"""
from alembic import op
import sqlalchemy as sa

revision = 'a5c1e7b3d9f2'
down_revision = 'f4b8d0c2e6a9'
branch_labels = None
depends_on = None


def upgrade():
    # SQLite me FK wala column add karne ke liye batch mode
    with op.batch_alter_table('production_orders') as batch:
        batch.add_column(sa.Column('extra_percent', sa.Float(), server_default='0', nullable=False))
        batch.add_column(sa.Column('short_action', sa.String(length=20), nullable=True))
        batch.add_column(sa.Column('short_note', sa.String(length=255), nullable=True))
        batch.add_column(sa.Column('short_resolved_at', sa.DateTime(), nullable=True))
        batch.add_column(sa.Column('balance_for_id', sa.Integer(), nullable=True))
        batch.create_foreign_key('fk_po_balance_for', 'production_orders', ['balance_for_id'], ['id'])


def downgrade():
    with op.batch_alter_table('production_orders') as batch:
        batch.drop_constraint('fk_po_balance_for', type_='foreignkey')
        batch.drop_column('balance_for_id')
        batch.drop_column('short_resolved_at')
        batch.drop_column('short_note')
        batch.drop_column('short_action')
        batch.drop_column('extra_percent')
