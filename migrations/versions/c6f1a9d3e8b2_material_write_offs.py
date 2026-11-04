"""material write offs (missing spools etc.)

Revision ID: c6f1a9d3e8b2
Revises: b5e8f2a1c4d6
Create Date: 2026-11-04 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c6f1a9d3e8b2'
down_revision = 'b5e8f2a1c4d6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'material_write_offs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('production_order_id', sa.Integer(), nullable=False),
        sa.Column('order_line_id', sa.Integer(), nullable=False),
        sa.Column('raw_material_id', sa.Integer(), nullable=False),
        sa.Column('qty', sa.Float(), nullable=False),
        sa.Column('reason', sa.String(length=255), nullable=False),
        sa.Column('written_off_by', sa.String(length=60), nullable=False),
        sa.Column('write_off_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['production_order_id'], ['production_orders.id']),
        sa.ForeignKeyConstraint(['order_line_id'], ['production_order_lines.id']),
        sa.ForeignKeyConstraint(['raw_material_id'], ['raw_materials.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('material_write_offs')
