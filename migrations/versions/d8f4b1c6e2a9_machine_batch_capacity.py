"""machines: batch capacity (KG per melt) + hours per batch (C8a)

Revision ID: d8f4b1c6e2a9
Revises: c7e3a9d5b1f4
Create Date: 2026-11-17
"""
from alembic import op
import sqlalchemy as sa

revision = "d8f4b1c6e2a9"
down_revision = "c7e3a9d5b1f4"
branch_labels = None
depends_on = None


def upgrade():
    # Dono nullable — purani machines (continuous) me khaali, kuch nahi badalta
    with op.batch_alter_table("machines", schema=None) as batch_op:
        batch_op.add_column(sa.Column("batch_capacity_kg", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("hours_per_batch", sa.Float(), nullable=True))


def downgrade():
    with op.batch_alter_table("machines", schema=None) as batch_op:
        batch_op.drop_column("hours_per_batch")
        batch_op.drop_column("batch_capacity_kg")
