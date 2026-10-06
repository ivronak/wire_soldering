"""customer state fk to state master

Revision ID: 454d9cf33d9d
Revises: f06cb680a4a6
Create Date: 2026-10-02 09:43:48.714139

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '454d9cf33d9d'
down_revision = 'f06cb680a4a6'
branch_labels = None
depends_on = None


def upgrade():
    # Step 1: naya `state_id` column pehle nullable add karo
    with op.batch_alter_table('customers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('state_id', sa.Integer(), sa.ForeignKey('states.id'), nullable=True))
    # Step 2: purane text `state` ko States ke naam se match karke state_id bharo
    op.get_bind().execute(sa.text(
        "UPDATE customers SET state_id = (SELECT id FROM states WHERE states.name = customers.state)"
    ))
    # Step 3: state_id NOT NULL + purana text `state` drop
    with op.batch_alter_table('customers', schema=None) as batch_op:
        batch_op.alter_column('state_id', existing_type=sa.Integer(), nullable=False)
        batch_op.drop_column('state')


def downgrade():
    with op.batch_alter_table('customers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('state', sa.String(length=50), nullable=True))
    op.get_bind().execute(sa.text(
        "UPDATE customers SET state = (SELECT name FROM states WHERE states.id = customers.state_id)"
    ))
    with op.batch_alter_table('customers', schema=None) as batch_op:
        batch_op.alter_column('state', existing_type=sa.String(length=50), nullable=False)
        batch_op.drop_column('state_id')
