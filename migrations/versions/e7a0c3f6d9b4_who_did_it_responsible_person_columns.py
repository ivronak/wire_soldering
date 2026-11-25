"""who did it - responsible person (W2) user_id columns (U4)

Revision ID: e7a0c3f6d9b4
Revises: d6f9b2e5c8a3
Create Date: 2026-11-24 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e7a0c3f6d9b4'
down_revision = 'd6f9b2e5c8a3'
branch_labels = None
depends_on = None

# W2 "zimmedar" (issued_by / received_by / returned_by / written_off_by / operator / recorded_by / inspector / tested_by):
# ab dropdown (Users) se chuna jaata hai — chuna hua user yahan `<field>_user_id` me, purana text column uska naam-snapshot rehta hai.
# Sirf nullable add — purane rows (text wale) jaise ke taise; purana code in columns ko jaanta hi nahi, rollback safe.
# Flow doc: user_in_erp_flow_2026_11_24.md (section 12).
COLUMNS = {
    "material_issues": ["issued_by_user_id", "received_by_user_id"],
    "material_returns": ["returned_by_user_id"],
    "material_write_offs": ["written_off_by_user_id"],
    "production_order_stages": ["operator_user_id"],
    "production_outputs": ["recorded_by_user_id"],
    "inward_qc": ["inspector_user_id"],
    "stage_lab_qc": ["tested_by_user_id"],
}


def upgrade():
    for table, names in COLUMNS.items():
        # SQLite me FK wala column jodne ke liye batch_alter_table (table recreate)
        with op.batch_alter_table(table, schema=None) as batch_op:
            for name in names:
                batch_op.add_column(sa.Column(name, sa.Integer(), sa.ForeignKey("users.id", name="fk_%s_%s" % (table, name)), nullable=True))


def downgrade():
    for table, names in COLUMNS.items():
        with op.batch_alter_table(table, schema=None) as batch_op:
            for name in names:
                batch_op.drop_constraint("fk_%s_%s" % (table, name), type_="foreignkey")
                batch_op.drop_column(name)
