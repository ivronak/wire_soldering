"""production order: reviewed flag (Finalize se bana order 'Needs review')

Revision ID: f8c3e0a4b6d5
Revises: e7b2d9f3a5c4
Create Date: 2026-11-20
"""
from alembic import op
import sqlalchemy as sa

revision = "f8c3e0a4b6d5"
down_revision = "e7b2d9f3a5c4"
branch_labels = None
depends_on = None


def upgrade():
    # Purane saare orders reviewed (1) — unka kaam pehle jaisa chalta rahega
    with op.batch_alter_table("production_orders") as batch:
        batch.add_column(sa.Column("reviewed", sa.Boolean(), nullable=False, server_default="1"))


def downgrade():
    with op.batch_alter_table("production_orders") as batch:
        batch.drop_column("reviewed")
