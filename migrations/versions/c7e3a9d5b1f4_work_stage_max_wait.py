"""work stage max wait minutes (C12)

Revision ID: c7e3a9d5b1f4
Revises: b6d2f8a4c1e7
Create Date: 2026-11-17
"""
from alembic import op
import sqlalchemy as sa

revision = "c7e3a9d5b1f4"
down_revision = "b6d2f8a4c1e7"
branch_labels = None
depends_on = None


def upgrade():
    # Nullable column — purane stages me khaali (koi limit nahi)
    with op.batch_alter_table("work_stage", schema=None) as batch_op:
        batch_op.add_column(sa.Column("max_wait_minutes", sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table("work_stage", schema=None) as batch_op:
        batch_op.drop_column("max_wait_minutes")
