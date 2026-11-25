"""who did it (actor) columns - procurement slice (U2)

Revision ID: b3d7f2a9c1e5
Revises: a9c4e1f6b2d8
Create Date: 2026-11-24 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b3d7f2a9c1e5'
down_revision = 'a9c4e1f6b2d8'
branch_labels = None
depends_on = None

# Procurement ke tables me "kisne kiya" ke naye NULLABLE columns (users.id FK). Purane rows NULL rehte hain (list me "—").
# Sirf add — koi data nahi badalta / hatta; purana code in columns ko jaanta hi nahi, isliye rollback safe.
# Flow doc: user_in_erp_flow_2026_11_24.md (W1 = login user se apne aap).
COLUMNS = {
    "purchase_orders": ["created_by_id", "confirmed_by_id", "short_closed_by_id"],
    "grns": ["created_by_id", "posted_by_id"],
    "inward_qc": ["created_by_id"],
    "rejection_memos": ["created_by_id"],
    "purchase_invoices": ["created_by_id", "posted_by_id", "cancelled_by_id"],
    "purchase_returns": ["created_by_id", "cancelled_by_id"],
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
