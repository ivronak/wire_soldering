"""Dashboard assign: stage ki machine badalne ka log (production_order_stage_machine_changes)

Revision ID: c3d9a5e7f1b4
Revises: b2f7d4a9c6e1
Create Date: 2026-11-23 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c3d9a5e7f1b4'
down_revision = 'b2f7d4a9c6e1'
branch_labels = None
depends_on = None


def upgrade():
    # Sirf nayi table: purana data nahi chhedta. Stage Start par machine badli to plan wali machine ki copy yahan rehti hai (history + Cancel run restore).
    op.create_table(
        'production_order_stage_machine_changes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stage_id', sa.Integer(), nullable=False),
        sa.Column('from_machine_id', sa.Integer(), nullable=True),
        sa.Column('from_machine_name', sa.String(length=100), nullable=True),
        sa.Column('from_capacity_per_hour', sa.Float(), nullable=True),
        sa.Column('from_hours_per_day', sa.Float(), nullable=True),
        sa.Column('to_machine_id', sa.Integer(), nullable=True),
        sa.Column('to_machine_name', sa.String(length=100), nullable=True),
        sa.Column('kind', sa.String(length=12), nullable=False),
        sa.Column('reason', sa.String(length=150), nullable=True),
        sa.Column('changed_at', sa.DateTime(), nullable=False),
        sa.Column('reverted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['stage_id'], ['production_order_stages.id']),
        sa.ForeignKeyConstraint(['from_machine_id'], ['machines.id']),
        sa.ForeignKeyConstraint(['to_machine_id'], ['machines.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('production_order_stage_machine_changes')
