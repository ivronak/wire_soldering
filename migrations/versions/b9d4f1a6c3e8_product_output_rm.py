"""product output goes to raw material stock (in-house product like Flux)

Revision ID: b9d4f1a6c3e8
Revises: a8c3e6f1b2d7
Create Date: 2026-11-13 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b9d4f1a6c3e8'
down_revision = 'a8c3e6f1b2d7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.add_column(sa.Column('output_rm_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_products_output_rm', 'raw_materials', ['output_rm_id'], ['id'])


def downgrade():
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.drop_constraint('fk_products_output_rm', type_='foreignkey')
        batch_op.drop_column('output_rm_id')
