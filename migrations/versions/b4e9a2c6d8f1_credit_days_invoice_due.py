"""sales S6: payment term credit days + sales invoice due date

Revision ID: b4e9a2c6d8f1
Revises: a3d8f1b5c7e9
Create Date: 2026-11-19
"""
from alembic import op
import sqlalchemy as sa

revision = "b4e9a2c6d8f1"
down_revision = "a3d8f1b5c7e9"
branch_labels = None
depends_on = None

# Purane seed terms ke credit days (naam se); aapke apne banaye terms me days khaali rahenge, master me bhar sakte ho
SEED_DAYS = {"Advance": 0, "Net 15": 15, "Net 30": 30, "Net 45": 45, "Net 60": 60, "Net 90": 90}


def upgrade():
    with op.batch_alter_table("payment_terms") as batch:
        batch.add_column(sa.Column("days", sa.Integer(), nullable=True))
    for name, days in SEED_DAYS.items():
        op.execute(sa.text("UPDATE payment_terms SET days = :d WHERE name = :n").bindparams(d=days, n=name))
    with op.batch_alter_table("sales_invoices") as batch:
        batch.add_column(sa.Column("due_date", sa.Date(), nullable=True))
    # Purane invoices: due date = invoice date + (quotation ke terms ke days, na ho to 0)
    op.execute(sa.text(
        "UPDATE sales_invoices SET due_date = date(invoice_date, '+' || COALESCE((SELECT pt.days FROM quotations q JOIN payment_terms pt ON pt.id = q.payment_terms_id "
        "WHERE q.id = sales_invoices.quotation_id), 0) || ' days')"))


def downgrade():
    with op.batch_alter_table("sales_invoices") as batch:
        batch.drop_column("due_date")
    with op.batch_alter_table("payment_terms") as batch:
        batch.drop_column("days")
