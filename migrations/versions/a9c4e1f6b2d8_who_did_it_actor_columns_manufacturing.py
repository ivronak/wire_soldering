"""who did it (actor) columns - manufacturing slice (U2)

Revision ID: a9c4e1f6b2d8
Revises: f7b1d4e8a2c6
Create Date: 2026-11-24 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a9c4e1f6b2d8'
down_revision = 'f7b1d4e8a2c6'
branch_labels = None
depends_on = None

# Har table me "kisne kiya" ke naye NULLABLE columns (users.id FK). Purane rows NULL rehte hain (list me "—").
# Sirf add — koi data nahi badalta / hatta; purana code in columns ko jaanta hi nahi, isliye rollback safe.
# Flow doc: user_in_erp_flow_2026_11_24.md (W1 = login user se apne aap).
COLUMNS = {
    "material_issues": ["created_by_id", "cancelled_by_id"],
    "material_returns": ["created_by_id", "cancelled_by_id"],
    "material_write_offs": ["created_by_id"],
    "production_orders": ["created_by_id", "released_by_id", "cancelled_by_id"],
    "production_order_stages": ["started_by_id", "completed_by_id"],
    "stage_lab_qc": ["created_by_id"],
    "production_outputs": ["created_by_id", "cancelled_by_id", "reviewed_by_id"],
    "machine_extra_hours": ["set_by_id"],
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
