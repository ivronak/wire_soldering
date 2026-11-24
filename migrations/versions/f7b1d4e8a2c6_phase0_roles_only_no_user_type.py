"""Phase 0: user "type" (kind) hata diya — ab sab kuch Role se. Developer + Admin bhi ordinary (system) roles.

- roles.system_key add ('developer' / 'admin' / NULL = custom role). System role ka naam / rights UI se badalte nahi.
- Developer + Admin role insert; purane users (kind=developer/admin) ko unke role par map.
- Baaki sab roles (6 starter) aur baaki sab users (staff) abhi ke liye hata diye (user ka faisla 23 Nov).
- users.kind column drop, users.role_id ab NOT NULL.

Revision ID: f7b1d4e8a2c6
Revises: e5f2c8b0d3a6
Create Date: 2026-11-23 23:30:00.000000

"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision = 'f7b1d4e8a2c6'
down_revision = 'e5f2c8b0d3a6'
branch_labels = None
depends_on = None


SYSTEM_ROLES = [
    ("developer", "Developer", "Owner account: every page with full edit. Only the server command can create it."),
    ("admin", "Admin", "Pages set on the Admin access screen. Manages users and roles."),
]


def upgrade():
    conn = op.get_bind()

    with op.batch_alter_table('roles') as batch_op:
        batch_op.add_column(sa.Column('system_key', sa.String(length=20), nullable=True))
        batch_op.create_unique_constraint('uq_roles_system_key', ['system_key'])

    # Agar kisi purane role ka naam "Developer" / "Admin" ho to naam khaali karo (system role ko ye naam chahiye)
    for _key, name, _desc in SYSTEM_ROLES:
        conn.execute(sa.text("UPDATE roles SET name = name || ' (old)' WHERE lower(name) = :n AND system_key IS NULL"), {"n": name.lower()})
    now = datetime.utcnow()
    for key, name, desc in SYSTEM_ROLES:
        conn.execute(sa.text(
            "INSERT INTO roles (name, description, is_starter, is_active, created_at, system_key) VALUES (:n, :d, 0, 1, :c, :k)"),
            {"n": name, "d": desc, "c": now, "k": key})

    # Purane users ko unke role par map karo (kind = developer / admin)
    for key, _name, _desc in SYSTEM_ROLES:
        conn.execute(sa.text("UPDATE users SET role_id = (SELECT id FROM roles WHERE system_key = :k) WHERE kind = :k"), {"k": key})

    # Staff users hatao (audit / created_by ke references pehle khaali)
    staff_ids = "(SELECT id FROM users WHERE kind NOT IN ('developer', 'admin'))"
    conn.execute(sa.text("UPDATE audit_log SET actor_user_id = NULL WHERE actor_user_id IN " + staff_ids))
    conn.execute(sa.text("UPDATE users SET created_by_id = NULL WHERE created_by_id IN " + staff_ids))
    conn.execute(sa.text("DELETE FROM users WHERE kind NOT IN ('developer', 'admin')"))
    # Baaki roles + unki permissions hatao
    conn.execute(sa.text("DELETE FROM role_permissions WHERE role_id IN (SELECT id FROM roles WHERE system_key IS NULL)"))
    conn.execute(sa.text("DELETE FROM roles WHERE system_key IS NULL"))

    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('kind')
        batch_op.alter_column('role_id', existing_type=sa.Integer(), nullable=False)


def downgrade():
    conn = op.get_bind()
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('kind', sa.String(length=10), nullable=False, server_default='staff'))
        batch_op.alter_column('role_id', existing_type=sa.Integer(), nullable=True)
    for key, _name, _desc in SYSTEM_ROLES:
        conn.execute(sa.text("UPDATE users SET kind = :k WHERE role_id = (SELECT id FROM roles WHERE system_key = :k)"), {"k": key})
        conn.execute(sa.text("UPDATE users SET role_id = NULL WHERE kind = :k"), {"k": key})
    # Custom roles wale users ka kind 'staff' hi rahega (default). System roles hata do.
    conn.execute(sa.text("DELETE FROM roles WHERE system_key IS NOT NULL"))
    with op.batch_alter_table('roles') as batch_op:
        batch_op.drop_constraint('uq_roles_system_key', type_='unique')
        batch_op.drop_column('system_key')
