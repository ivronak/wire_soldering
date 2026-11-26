"""accounts A1 - chart of accounts tree + system ledgers + vouchers / voucher_entries

Revision ID: f8c2d5a1e9b6
Revises: e7a0c3f6d9b4
Create Date: 2026-11-25 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

from app.accounts.chart import GROUPS, SYSTEM_LEDGERS


# revision identifiers, used by Alembic.
revision = 'f8c2d5a1e9b6'
down_revision = 'e7a0c3f6d9b4'
branch_labels = None
depends_on = None

# Sirf ADD: 2 naye tables + group / ledger me nullable ya default wale columns + starter chart rows.
# Purane Customer / Vendor ledgers aur unke balance ko ye migration chhoota nahi. Flow doc: accounts_flow_2026_11_25.md


def upgrade():
    with op.batch_alter_table("chart_of_accounts_groups", schema=None) as batch_op:
        batch_op.add_column(sa.Column("parent_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("is_system", sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.create_foreign_key("fk_coa_groups_parent", "chart_of_accounts_groups", ["parent_id"], ["id"])
    with op.batch_alter_table("ledgers", schema=None) as batch_op:
        batch_op.add_column(sa.Column("system_key", sa.String(40), nullable=True))
        batch_op.add_column(sa.Column("is_system", sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.add_column(sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False))
        batch_op.create_unique_constraint("uq_ledgers_system_key", ["system_key"])

    op.create_table(
        "vouchers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("voucher_no", sa.String(24), nullable=False),
        sa.Column("voucher_type", sa.String(20), nullable=False),
        sa.Column("voucher_date", sa.Date(), nullable=False),
        sa.Column("narration", sa.String(255), nullable=True),
        sa.Column("source_type", sa.String(30), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(12), server_default="Posted", nullable=False),
        sa.Column("reverses_voucher_id", sa.Integer(), sa.ForeignKey("vouchers.id", name="fk_vouchers_reverses"), nullable=True),
        sa.Column("reversal_reason", sa.String(255), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", name="fk_vouchers_created_by"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("voucher_no", name="uq_vouchers_voucher_no"),
    )
    op.create_index("ix_vouchers_source", "vouchers", ["source_type", "source_id"])
    op.create_table(
        "voucher_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("voucher_id", sa.Integer(), sa.ForeignKey("vouchers.id", name="fk_ventries_voucher"), nullable=False),
        sa.Column("ledger_id", sa.Integer(), sa.ForeignKey("ledgers.id", name="fk_ventries_ledger"), nullable=False),
        sa.Column("side", sa.String(2), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("narration", sa.String(255), nullable=True),
    )
    op.create_index("ix_voucher_entries_voucher_id", "voucher_entries", ["voucher_id"])
    op.create_index("ix_voucher_entries_ledger_id", "voucher_entries", ["ledger_id"])

    # ---- starter chart seed ----
    conn = op.get_bind()
    groups = sa.table("chart_of_accounts_groups", sa.column("id", sa.Integer), sa.column("name", sa.String), sa.column("classification", sa.String),
                      sa.column("parent_id", sa.Integer), sa.column("is_system", sa.Boolean), sa.column("created_at", sa.DateTime))
    ledgers = sa.table("ledgers", sa.column("id", sa.Integer), sa.column("name", sa.String), sa.column("group_id", sa.Integer),
                       sa.column("opening_balance", sa.Float), sa.column("opening_balance_type", sa.String), sa.column("current_balance", sa.Float),
                       sa.column("system_key", sa.String), sa.column("is_system", sa.Boolean), sa.column("is_active", sa.Boolean),
                       sa.column("created_at", sa.DateTime))
    ids = {}
    now = sa.func.current_timestamp()
    for name, classification, parent in GROUPS:
        row = conn.execute(sa.select(groups.c.id).where(groups.c.name == name)).first()      # Sundry Debtors / Creditors pehle se ho sakte hain
        parent_id = ids.get(parent) if parent else None
        if row:
            ids[name] = row[0]
            conn.execute(groups.update().where(groups.c.id == row[0]).values(parent_id=parent_id, is_system=True))
        else:
            conn.execute(groups.insert().values(name=name, classification=classification, parent_id=parent_id, is_system=True, created_at=now))
            ids[name] = conn.execute(sa.select(groups.c.id).where(groups.c.name == name)).scalar()
    for key, name, group in SYSTEM_LEDGERS:
        conn.execute(ledgers.insert().values(name=name, group_id=ids[group], opening_balance=0, opening_balance_type="Cr", current_balance=0,
                                             system_key=key, is_system=True, is_active=True, created_at=now))


def downgrade():
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM ledgers WHERE is_system = 1"))        # sirf seed hue system ledgers (party ledgers is_system = 0 hain)
    op.drop_index("ix_voucher_entries_ledger_id", table_name="voucher_entries")
    op.drop_index("ix_voucher_entries_voucher_id", table_name="voucher_entries")
    op.drop_table("voucher_entries")
    op.drop_index("ix_vouchers_source", table_name="vouchers")
    op.drop_table("vouchers")
    with op.batch_alter_table("ledgers", schema=None) as batch_op:
        batch_op.drop_constraint("uq_ledgers_system_key", type_="unique")
        batch_op.drop_column("is_active")
        batch_op.drop_column("is_system")
        batch_op.drop_column("system_key")
    with op.batch_alter_table("chart_of_accounts_groups", schema=None) as batch_op:
        batch_op.drop_constraint("fk_coa_groups_parent", type_="foreignkey")
        batch_op.drop_column("is_system")
        batch_op.drop_column("parent_id")
    # Seed groups hata do jo ab khaali hain (Sundry Debtors / Creditors ko chhod ke: wo Customer / Vendor ke hain)
    conn.execute(sa.text("DELETE FROM chart_of_accounts_groups WHERE name NOT IN ('Sundry Debtors', 'Sundry Creditors') AND id NOT IN (SELECT group_id FROM ledgers)"))
