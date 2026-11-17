"""melt groups: heat number + combine same-alloy Melting stages (C9 phase 2)

Revision ID: e9a5c2d7f3b8
Revises: d8f4b1c6e2a9
Create Date: 2026-11-17
"""
from alembic import op
import sqlalchemy as sa

revision = "e9a5c2d7f3b8"
down_revision = "d8f4b1c6e2a9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "melt_groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("heat_no", sa.String(length=20), nullable=False),
        sa.Column("work_stage_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["work_stage_id"], ["work_stage.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("heat_no"),
    )
    with op.batch_alter_table("production_order_stages", schema=None) as batch_op:
        batch_op.add_column(sa.Column("melt_group_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_stage_melt_group_id", "melt_groups", ["melt_group_id"], ["id"])


def downgrade():
    with op.batch_alter_table("production_order_stages", schema=None) as batch_op:
        batch_op.drop_constraint("fk_stage_melt_group_id", type_="foreignkey")
        batch_op.drop_column("melt_group_id")
    op.drop_table("melt_groups")
