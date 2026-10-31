"""work stage scrap_after_next flag

Revision ID: b7c41d2e9a10
Revises: eaa08ad0724e
Create Date: 2026-10-30 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7c41d2e9a10'
down_revision = 'eaa08ad0724e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('work_stage', schema=None) as batch_op:
        batch_op.add_column(sa.Column('scrap_after_next', sa.Boolean(), server_default=sa.text('0'), nullable=False))


def downgrade():
    with op.batch_alter_table('work_stage', schema=None) as batch_op:
        batch_op.drop_column('scrap_after_next')
