"""product master: Extra % for scrap (default for production orders)

Revision ID: e7b2d9f3a5c4
Revises: d6a1c8e2f4b3
Create Date: 2026-11-20
"""
from alembic import op
import sqlalchemy as sa

revision = "e7b2d9f3a5c4"
down_revision = "d6a1c8e2f4b3"
branch_labels = None
depends_on = None


def upgrade():
    # Purane products par 0 (extra nahi) — pehle jaisa hi chalega
    with op.batch_alter_table("products") as batch:
        batch.add_column(sa.Column("scrap_extra_percent", sa.Float(), nullable=False, server_default="0"))


def downgrade():
    with op.batch_alter_table("products") as batch:
        batch.drop_column("scrap_extra_percent")
