"""sales S4: sales invoices (+ lines, charges) and challan -> invoice link

Revision ID: f2c7e9a1b3d5
Revises: e6b8d0f2a4c5
Create Date: 2026-11-18
"""
from alembic import op
import sqlalchemy as sa

revision = "f2c7e9a1b3d5"
down_revision = "e6b8d0f2a4c5"
branch_labels = None
depends_on = None


def upgrade():
    # Teen naye table + delivery_challans par ek naya nullable column (purane challan "bill nahi bana" maane jaate hain)
    op.create_table(
        "sales_invoices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("invoice_no", sa.String(20), nullable=False, unique=True),
        sa.Column("quotation_id", sa.Integer(), sa.ForeignKey("quotations.id"), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("tax_type", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="Posted"),
        sa.Column("remarks", sa.String(255), nullable=True),
        sa.Column("subtotal", sa.Float(), nullable=False, server_default="0"),
        sa.Column("charges_total", sa.Float(), nullable=False, server_default="0"),
        sa.Column("tax_total", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("cost_total", sa.Float(), nullable=False, server_default="0"),
        sa.Column("has_loss", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("loss_amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("loss_note", sa.String(255), nullable=True),
        sa.Column("loss_approved_at", sa.DateTime(), nullable=True),
        sa.Column("cancel_reason", sa.String(255), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.create_table(
        "sales_invoice_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("sales_invoices.id"), nullable=False),
        sa.Column("quotation_line_id", sa.Integer(), sa.ForeignKey("quotation_lines.id"), nullable=False),
        sa.Column("qty", sa.Float(), nullable=False),
        sa.Column("rate", sa.Float(), nullable=False),
        sa.Column("discount_percent", sa.Float(), nullable=False, server_default="0"),
        sa.Column("tax_rate_id", sa.Integer(), sa.ForeignKey("tax_rates.id"), nullable=True),
        sa.Column("unit_cost", sa.Float(), nullable=False, server_default="0"),
    )
    op.create_table(
        "sales_invoice_charges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("sales_invoices.id"), nullable=False),
        sa.Column("charge_id", sa.Integer(), sa.ForeignKey("charges.id"), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("effect", sa.String(10), nullable=False),
    )
    with op.batch_alter_table("delivery_challans") as batch:
        batch.add_column(sa.Column("invoice_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_delivery_challans_invoice", "sales_invoices", ["invoice_id"], ["id"])


def downgrade():
    with op.batch_alter_table("delivery_challans") as batch:
        batch.drop_constraint("fk_delivery_challans_invoice", type_="foreignkey")
        batch.drop_column("invoice_id")
    op.drop_table("sales_invoice_charges")
    op.drop_table("sales_invoice_lines")
    op.drop_table("sales_invoices")
