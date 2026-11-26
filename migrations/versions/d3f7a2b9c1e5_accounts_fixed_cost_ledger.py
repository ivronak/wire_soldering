"""accounts - Fixed Cost Payable system ledger (production fixed cost ka voucher)

Revision ID: d3f7a2b9c1e5
Revises: b5e2f8a1d4c6
Create Date: 2026-11-25 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd3f7a2b9c1e5'
down_revision = 'b5e2f8a1d4c6'
branch_labels = None
depends_on = None

# Sirf ek system ledger ADD: "Fixed Cost Payable" (Current Liabilities me). Pehle se ho (A1 naye chart se bana ho) to kuch nahi karta.


def upgrade():
    conn = op.get_bind()
    groups = sa.table("chart_of_accounts_groups", sa.column("id", sa.Integer), sa.column("name", sa.String))
    ledgers = sa.table("ledgers", sa.column("id", sa.Integer), sa.column("name", sa.String), sa.column("group_id", sa.Integer),
                       sa.column("opening_balance", sa.Float), sa.column("opening_balance_type", sa.String), sa.column("current_balance", sa.Float),
                       sa.column("system_key", sa.String), sa.column("is_system", sa.Boolean), sa.column("is_active", sa.Boolean),
                       sa.column("created_at", sa.DateTime))
    if conn.execute(sa.select(ledgers.c.id).where(ledgers.c.system_key == "fixed_cost_payable")).first():
        return
    group_id = conn.execute(sa.select(groups.c.id).where(groups.c.name == "Current Liabilities")).scalar()
    conn.execute(ledgers.insert().values(name="Fixed Cost Payable", group_id=group_id, opening_balance=0, opening_balance_type="Cr", current_balance=0,
                                         system_key="fixed_cost_payable", is_system=True, is_active=True, created_at=sa.func.current_timestamp()))


def downgrade():
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM ledgers WHERE system_key = 'fixed_cost_payable' AND id NOT IN (SELECT ledger_id FROM voucher_entries)"))
