"""Phase 0 P0-1: users, roles, role_permissions, admin_ceiling, audit_log + 6 starter roles

Revision ID: d4e1b7a9c2f5
Revises: c3d9a5e7f1b4
Create Date: 2026-11-23 20:00:00.000000

"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision = 'd4e1b7a9c2f5'
down_revision = 'c3d9a5e7f1b4'
branch_labels = None
depends_on = None


V, E = 1, 2   # View, View + Edit

# 6 starter roles (user ka faisla 23 Nov) — shuru ka sample, Admin baad me edit / copy kar sakta hai.
# Migration apne me poori hai (app code import nahi karti) taaki baad me registry badle to ye purani migration na toote.
# Cost / profit wale pages (costing, profit, valuation, variance) Read-only aur Accounts ko nahi diye (client: accounts wale ko costing nahi dikhani).
# stock_adjustments.approve kisi starter role me nahi (sirf Admin / Developer).
_ALL_PAGES = [
    "dashboard", "units", "tax_rates", "charges", "states", "payment_terms", "payment_modes", "work_stages", "machines", "production_lines",
    "rm_categories", "raw_materials", "product_categories", "products", "warehouses", "racks", "vendors", "vendor_types", "customers",
    "purchase_orders", "grns", "inward_qc", "purchase_invoices", "purchase_returns",
    "quotations", "dispatch", "invoices", "receipts", "sales_returns", "receivables", "statement", "profit",
    "stock", "opening_stock", "stock_transfers", "stock_adjustments", "valuation", "finished_goods",
    "production_orders", "production_planning", "material_plan", "material_issues", "routing", "production_output", "scrap", "variance", "costing",
]
_COST_PAGES = {"costing", "profit", "valuation", "variance"}

STARTER_ROLES = [
    ("Store keeper", "Gate inward, stock, issue and transfers", {
        "grns": E, "inward_qc": V, "stock": V, "opening_stock": E, "stock_transfers": E, "stock_adjustments": E, "material_issues": E,
        "warehouses": V, "racks": V, "raw_materials": V, "finished_goods": V, "units": V, "purchase_orders": V}),
    ("Purchase", "Vendors, purchase orders, invoices and returns", {
        "vendors": E, "vendor_types": V, "purchase_orders": E, "grns": V, "inward_qc": V, "purchase_invoices": E, "purchase_returns": E,
        "raw_materials": V, "rm_categories": V, "tax_rates": V, "charges": V, "payment_terms": V, "units": V, "material_plan": V, "stock": V}),
    ("Sales", "Customers, quotations, dispatch, invoices and receipts", {
        "customers": E, "quotations": E, "dispatch": E, "invoices": E, "receipts": E, "sales_returns": E, "receivables": V, "statement": V,
        "products": V, "finished_goods": V, "states": V, "payment_terms": V, "payment_modes": V, "charges": V, "tax_rates": V}),
    ("Production supervisor", "Orders, planning, routing, output and scrap on the shop floor", {
        "dashboard": E, "production_orders": E, "production_planning": E, "material_plan": V, "material_issues": E, "routing": E,
        "production_output": E, "scrap": E, "machines": V, "work_stages": V, "production_lines": V, "products": V, "finished_goods": V,
        "stock": V, "raw_materials": V}),
    ("Accounts", "Bills, receipts, statements and ledgers (no costing)", {
        "invoices": V, "receipts": E, "receivables": V, "statement": V, "sales_returns": V, "quotations": V, "customers": V, "vendors": V,
        "purchase_invoices": E, "purchase_returns": V, "purchase_orders": V, "payment_terms": V, "payment_modes": V, "tax_rates": V, "charges": V}),
    ("Read-only", "Can view everything except cost and profit pages", {p: V for p in _ALL_PAGES if p not in _COST_PAGES}),
]


def upgrade():
    # Sirf nayi tables + 6 starter roles: purana data nahi chhedta.
    op.create_table(
        'roles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=60), nullable=False),
        sa.Column('description', sa.String(length=200), nullable=True),
        sa.Column('is_starter', sa.Boolean(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('full_name', sa.String(length=100), nullable=False),
        sa.Column('mobile', sa.String(length=15), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('kind', sa.String(length=10), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('must_change_password', sa.Boolean(), nullable=False),
        sa.Column('session_version', sa.Integer(), nullable=False),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id']),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('mobile'),
    )
    op.create_table(
        'role_permissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('page_key', sa.String(length=60), nullable=False),
        sa.Column('level', sa.Integer(), nullable=False),
        sa.CheckConstraint('level IN (1, 2)', name='ck_role_permissions_level'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('role_id', 'page_key', name='uq_role_permissions_role_page'),
    )
    op.create_table(
        'admin_ceiling',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('page_key', sa.String(length=60), nullable=False),
        sa.Column('level', sa.Integer(), nullable=False),
        sa.CheckConstraint('level IN (1, 2)', name='ck_admin_ceiling_level'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('page_key'),
    )
    op.create_table(
        'audit_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('at', sa.DateTime(), nullable=False),
        sa.Column('actor_user_id', sa.Integer(), nullable=True),
        sa.Column('actor_label', sa.String(length=100), nullable=True),
        sa.Column('action', sa.String(length=40), nullable=False),
        sa.Column('target_type', sa.String(length=30), nullable=True),
        sa.Column('target_id', sa.Integer(), nullable=True),
        sa.Column('detail', sa.Text(), nullable=True),
        sa.Column('ip', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('audit_log') as batch_op:
        batch_op.create_index('ix_audit_log_at', ['at'])
        batch_op.create_index('ix_audit_log_action', ['action'])

    # 6 starter roles + unki permissions (data seed)
    roles_t = sa.table('roles', sa.column('id', sa.Integer), sa.column('name', sa.String), sa.column('description', sa.String),
                       sa.column('is_starter', sa.Boolean), sa.column('is_active', sa.Boolean), sa.column('created_at', sa.DateTime))
    perm_t = sa.table('role_permissions', sa.column('role_id', sa.Integer), sa.column('page_key', sa.String), sa.column('level', sa.Integer))
    now = datetime.utcnow()
    conn = op.get_bind()
    for name, desc, perms in STARTER_ROLES:
        conn.execute(roles_t.insert().values(name=name, description=desc, is_starter=True, is_active=True, created_at=now))
        role_id = conn.execute(sa.text("SELECT id FROM roles WHERE name = :n"), {"n": name}).scalar()
        for key, level in perms.items():
            conn.execute(perm_t.insert().values(role_id=role_id, page_key=key, level=level))


def downgrade():
    op.drop_table('audit_log')
    op.drop_table('admin_ceiling')
    op.drop_table('role_permissions')
    op.drop_table('users')
    op.drop_table('roles')
