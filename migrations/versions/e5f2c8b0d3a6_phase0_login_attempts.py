"""Phase 0 P0-2: login_attempts (lockout counter per mobile-hash + IP)

Revision ID: e5f2c8b0d3a6
Revises: d4e1b7a9c2f5
Create Date: 2026-11-23 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'e5f2c8b0d3a6'
down_revision = 'd4e1b7a9c2f5'
branch_labels = None
depends_on = None


def upgrade():
    # Nayi table, purana data nahi chhedta
    op.create_table(
        'login_attempts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('mobile_hash', sa.String(length=64), nullable=False),
        sa.Column('ip', sa.String(length=45), nullable=False),
        sa.Column('failed_count', sa.Integer(), nullable=False),
        sa.Column('locked_until', sa.DateTime(), nullable=True),
        sa.Column('last_failed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('mobile_hash', 'ip', name='uq_login_attempts_mobile_ip'),
    )


def downgrade():
    op.drop_table('login_attempts')
