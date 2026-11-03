"""scrap packs

Revision ID: a6d3b8c1e4f7
Revises: f4d7a9b1c3e5
Create Date: 2026-10-31 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a6d3b8c1e4f7'
down_revision = 'f4d7a9b1c3e5'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('scrap_packs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('pack_no', sa.String(length=20), nullable=False),
        sa.Column('pack_date', sa.Date(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('pack_no'))
    op.create_table('scrap_pack_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('pack_id', sa.Integer(), nullable=False),
        sa.Column('batch_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['batch_id'], ['fg_batches.id']),
        sa.ForeignKeyConstraint(['pack_id'], ['scrap_packs.id']),
        sa.PrimaryKeyConstraint('id'))


def downgrade():
    op.drop_table('scrap_pack_items')
    op.drop_table('scrap_packs')
