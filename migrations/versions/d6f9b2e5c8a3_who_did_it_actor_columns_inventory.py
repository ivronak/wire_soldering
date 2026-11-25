"""who did it (actor) columns - inventory slice (U2)

Revision ID: d6f9b2e5c8a3
Revises: c5e8a1d4b7f2
Create Date: 2026-11-24 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd6f9b2e5c8a3'
down_revision = 'c5e8a1d4b7f2'
branch_labels = None
depends_on = None

# Inventory ke tables me "kisne kiya" ke naye NULLABLE columns (users.id FK). Purane rows NULL rehte hain (list me "—").
# Sirf add — koi data nahi badalta / hatta; purana code in columns ko jaanta hi nahi, isliye rollback safe.
# Flow doc: user_in_erp_flow_2026_11_24.md (W1 = login user se apne aap).
COLUMNS = {
    "stock_transfers": ["created_by_id", "dispatched_by_id", "received_by_id", "cancelled_by_id"],
    "stock_adjustments": ["created_by_id", "submitted_by_id", "approved_by_id", "cancelled_by_id"],
    "opening_stocks": ["created_by_id", "posted_by_id", "cancelled_by_id"],
    "scrap_packs": ["created_by_id", "unpacked_by_id"],
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
