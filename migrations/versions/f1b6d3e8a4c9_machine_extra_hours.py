"""machine extra hours: night / extra shift on one day (C10)

Revision ID: f1b6d3e8a4c9
Revises: e9a5c2d7f3b8
Create Date: 2026-11-17
"""
from alembic import op
import sqlalchemy as sa

revision = "f1b6d3e8a4c9"
down_revision = "e9a5c2d7f3b8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "machine_extra_hours",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("machine_id", sa.Integer(), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("extra_hours", sa.Float(), nullable=False),
        sa.Column("reason", sa.String(length=120), nullable=True),
        sa.Column("set_by", sa.String(length=60), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["machine_id"], ["machines.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("machine_id", "work_date", name="uq_machine_extra_hours_day"),
    )


def downgrade():
    op.drop_table("machine_extra_hours")
