"""fixed costing: monthly fixed cost periods, month finalize, fixed cost on production output

Revision ID: f4b8d0c2e6a9
Revises: e3a7c9b1d5f8
Create Date: 2026-11-14 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f4b8d0c2e6a9'
down_revision = 'e3a7c9b1d5f8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('fixed_cost_periods',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('effective_from', sa.Date(), nullable=False),
        sa.Column('monthly_amount', sa.Float(), nullable=False),
        sa.Column('working_days', sa.Integer(), nullable=False),
        sa.Column('note', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'))
    op.create_table('fixed_cost_months',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('month_start', sa.Date(), nullable=False),
        sa.Column('final_amount', sa.Float(), nullable=False),
        sa.Column('total_kg', sa.Float(), nullable=False),
        sa.Column('final_per_kg', sa.Float(), nullable=False),
        sa.Column('finalized_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('month_start'))
    # Purane outputs: fixed cost 0 aur basis khaali = "Material only" (unka cost badalta nahi)
    with op.batch_alter_table('production_outputs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('fixed_cost_per_kg', sa.Float(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('fixed_cost_total', sa.Float(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('fixed_cost_basis', sa.String(length=8), nullable=True))


def downgrade():
    with op.batch_alter_table('production_outputs', schema=None) as batch_op:
        batch_op.drop_column('fixed_cost_basis')
        batch_op.drop_column('fixed_cost_total')
        batch_op.drop_column('fixed_cost_per_kg')
    op.drop_table('fixed_cost_months')
    op.drop_table('fixed_cost_periods')
