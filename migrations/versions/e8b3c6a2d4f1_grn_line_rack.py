"""grn line rack

Revision ID: e8b3c6a2d4f1
Revises: d5e2a1b7c9f4
Create Date: 2026-10-31 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e8b3c6a2d4f1'
down_revision = 'd5e2a1b7c9f4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('grn_lines', schema=None) as batch_op:
        batch_op.add_column(sa.Column('rack_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_grn_lines_rack_id', 'racks', ['rack_id'], ['id'])


def downgrade():
    with op.batch_alter_table('grn_lines', schema=None) as batch_op:
        batch_op.drop_constraint('fk_grn_lines_rack_id', type_='foreignkey')
        batch_op.drop_column('rack_id')
