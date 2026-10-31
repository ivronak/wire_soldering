"""fg batch rack

Revision ID: f4d7a9b1c3e5
Revises: e8b3c6a2d4f1
Create Date: 2026-10-31 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f4d7a9b1c3e5'
down_revision = 'e8b3c6a2d4f1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('fg_batches', schema=None) as batch_op:
        batch_op.add_column(sa.Column('rack_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_fg_batches_rack_id', 'racks', ['rack_id'], ['id'])


def downgrade():
    with op.batch_alter_table('fg_batches', schema=None) as batch_op:
        batch_op.drop_constraint('fk_fg_batches_rack_id', type_='foreignkey')
        batch_op.drop_column('rack_id')
