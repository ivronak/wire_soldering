"""who did it (actor) columns - sales slice (U2)

Revision ID: c5e8a1d4b7f2
Revises: b3d7f2a9c1e5
Create Date: 2026-11-24 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c5e8a1d4b7f2'
down_revision = 'b3d7f2a9c1e5'
branch_labels = None
depends_on = None

# Sales ke tables me "kisne kiya" ke naye NULLABLE columns (users.id FK). Purane rows NULL rehte hain (list me "—").
# Sirf add — koi data nahi badalta / hatta; purana code in columns ko jaanta hi nahi, isliye rollback safe.
# Flow doc: user_in_erp_flow_2026_11_24.md (W1 = login user se apne aap).
COLUMNS = {
    "quotations": ["created_by_id", "status_by_id", "finalized_by_id"],
    "quotation_revisions": ["created_by_id"],
    "delivery_challans": ["created_by_id", "cancelled_by_id"],
    "sales_invoices": ["created_by_id", "loss_approved_by_id", "cancelled_by_id"],
    "sales_receipts": ["created_by_id", "cancelled_by_id"],
    "sales_returns": ["created_by_id", "cancelled_by_id"],
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
