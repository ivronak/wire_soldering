"""payment terms fk to payment terms master

Revision ID: c9b2e5d47a18
Revises: 2d072240cf0f
Create Date: 2026-10-02 06:25:00.000000

Vendor / Customer / PurchaseOrder — teeno ka purana free-text `payment_terms`
column hata kar Payment Terms Master (payment_terms) ka FK bana rahe hain.
Teeno OPTIONAL (nullable) — user ne decide kiya.
STEP 1: nullable payment_terms_id add -> purane text value ko master ke naam se
match karke backfill -> purana text column drop. (Teeno tables ek hi migration me.)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c9b2e5d47a18'
down_revision = '2d072240cf0f'
branch_labels = None
depends_on = None


# Jitni tables me purana free-text `payment_terms` column hai
TABLES = ['vendors', 'customers', 'purchase_orders']


def upgrade():
    # Teeno tables pe same 3-step pattern chalega.
    # SQLite me column add/drop ke liye batch_alter_table (table recreate) chahiye.
    for table in TABLES:
        # Step 1: naya `payment_terms_id` nullable add karo (backfill se PEHLE)
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column('payment_terms_id', sa.Integer(),
                                          sa.ForeignKey('payment_terms.id'), nullable=True))

        # Step 2: purane text value ko payment_terms ke naam se match karke id bharo
        op.get_bind().execute(sa.text(
            "UPDATE {t} SET payment_terms_id = "
            "(SELECT id FROM payment_terms WHERE payment_terms.name = {t}.payment_terms) "
            "WHERE payment_terms IS NOT NULL AND TRIM(payment_terms) <> ''".format(t=table)
        ))

        # Step 3: purana text `payment_terms` column hata do (ab master FK use ho raha hai)
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column('payment_terms')


def downgrade():
    # Ulta: wapas text `payment_terms` column, naam payment_terms table se le kar
    for table in TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column('payment_terms', sa.String(length=100), nullable=True))

        op.get_bind().execute(sa.text(
            "UPDATE {t} SET payment_terms = "
            "(SELECT name FROM payment_terms WHERE payment_terms.id = {t}.payment_terms_id)".format(t=table)
        ))

        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column('payment_terms_id')
