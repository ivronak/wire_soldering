"""vendor state fk to state master

Revision ID: f06cb680a4a6
Revises: fd2c563b95f7
Create Date: 2026-10-02 09:25:50.732931

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f06cb680a4a6'
down_revision = 'fd2c563b95f7'
branch_labels = None
depends_on = None


def upgrade():
    # Vendor ka purana free-text `state` column ab State Master ka FK ban raha hai.
    # SQLite me column add/drop/alter ke liye batch_alter_table (table recreate) chahiye.

    # Step 1: naya `state_id` column pehle nullable add karo (backfill se PEHLE, warna NOT NULL fill nahi hoga)
    with op.batch_alter_table('vendors', schema=None) as batch_op:
        batch_op.add_column(sa.Column('state_id', sa.Integer(), sa.ForeignKey('states.id'), nullable=True))

    # Step 2: purane text `state` ko States ke naam se match karke state_id bharo
    op.get_bind().execute(sa.text(
        "UPDATE vendors SET state_id = "
        "(SELECT id FROM states WHERE states.name = vendors.state)"
    ))

    # Step 3: ab state_id NOT NULL karo aur purana text `state` column hata do
    with op.batch_alter_table('vendors', schema=None) as batch_op:
        batch_op.alter_column('state_id', existing_type=sa.Integer(), nullable=False)
        batch_op.drop_column('state')


def downgrade():
    # Ulta: wapas text `state` column, naam States table se le kar
    with op.batch_alter_table('vendors', schema=None) as batch_op:
        batch_op.add_column(sa.Column('state', sa.String(length=50), nullable=True))

    op.get_bind().execute(sa.text(
        "UPDATE vendors SET state = "
        "(SELECT name FROM states WHERE states.id = vendors.state_id)"
    ))

    with op.batch_alter_table('vendors', schema=None) as batch_op:
        batch_op.alter_column('state', existing_type=sa.String(length=50), nullable=False)
        batch_op.drop_column('state_id')
