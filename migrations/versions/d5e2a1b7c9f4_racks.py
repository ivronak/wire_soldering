"""racks master

Revision ID: d5e2a1b7c9f4
Revises: c3a9f5d8e1b2
Create Date: 2026-10-31 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd5e2a1b7c9f4'
down_revision = 'c3a9f5d8e1b2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('racks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=20), nullable=False),
    sa.Column('name', sa.String(length=40), nullable=False),
    sa.Column('warehouse_id', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id'], name=op.f('fk_racks_warehouse_id_warehouses')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_racks')),
    sa.UniqueConstraint('code', name=op.f('uq_racks_code'))
    )


def downgrade():
    op.drop_table('racks')
