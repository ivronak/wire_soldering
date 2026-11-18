"""sales S1.2: quotation revisions (R1, R2 ... inside the same quotation number)

Revision ID: c4f6b8d0e2a3
Revises: b3e5a7c9d1f2
Create Date: 2026-11-18
"""
from alembic import op
import sqlalchemy as sa

revision = "c4f6b8d0e2a3"
down_revision = "b3e5a7c9d1f2"
branch_labels = None
depends_on = None


def upgrade():
    # Sirf naya table
    op.create_table(
        "quotation_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("quotation_id", sa.Integer(), sa.ForeignKey("quotations.id"), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(255), nullable=False),
        sa.Column("changes", sa.Text(), nullable=True),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("old_total", sa.Float(), nullable=True),
        sa.Column("new_total", sa.Float(), nullable=True),
    )


def downgrade():
    op.drop_table("quotation_revisions")
