"""vendor type fk to vendor type master

Revision ID: d4e6f8a0b2c3
Revises: b7e4c2a91f38
Create Date: 2026-10-02 05:45:00.000000

Vendor ka purana free-text `vendor_type` column hata kar Vendor Type Master
(vendor_types) ka FK bana rahe hain. OPTIONAL (nullable) — user ne decide kiya.
STEP 1: nullable vendor_type_id add -> purane text value ko master ke naam se
match karke backfill -> purana text column drop.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4e6f8a0b2c3'
down_revision = 'b7e4c2a91f38'
branch_labels = None
depends_on = None


def upgrade():
    # Vendor ka purana free-text `vendor_type` ab Vendor Type Master ka FK ban raha hai.
    # SQLite me column add/drop ke liye batch_alter_table (table recreate) chahiye.

    # Step 1: naya `vendor_type_id` nullable add karo (backfill se PEHLE)
    with op.batch_alter_table('vendors', schema=None) as batch_op:
        batch_op.add_column(sa.Column('vendor_type_id', sa.Integer(),
                                      sa.ForeignKey('vendor_types.id'), nullable=True))

    # Step 2: purane text value ko vendor_types ke naam se match karke vendor_type_id bharo
    op.get_bind().execute(sa.text(
        "UPDATE vendors SET vendor_type_id = "
        "(SELECT id FROM vendor_types WHERE vendor_types.name = vendors.vendor_type) "
        "WHERE vendor_type IS NOT NULL AND TRIM(vendor_type) <> ''"
    ))

    # Step 3: purana text `vendor_type` column hata do (ab master FK use ho raha hai)
    with op.batch_alter_table('vendors', schema=None) as batch_op:
        batch_op.drop_column('vendor_type')


def downgrade():
    # Ulta: wapas text `vendor_type` column, naam vendor_types table se le kar
    with op.batch_alter_table('vendors', schema=None) as batch_op:
        batch_op.add_column(sa.Column('vendor_type', sa.String(length=30), nullable=True))

    op.get_bind().execute(sa.text(
        "UPDATE vendors SET vendor_type = "
        "(SELECT name FROM vendor_types WHERE vendor_types.id = vendors.vendor_type_id)"
    ))

    with op.batch_alter_table('vendors', schema=None) as batch_op:
        batch_op.drop_column('vendor_type_id')
