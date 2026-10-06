"""vendor type master

Revision ID: b7e4c2a91f38
Revises: f5b57613d924
Create Date: 2026-10-02 05:25:00.000000

Vendor Type dropdown ka apna master banaya. Pehle ye Vendor form me hardcoded
tha (5 options) — ab ye table hai, aur wahi 5 options yahan seed kar diye taaki
Step 1 me Vendor ka backfill clean ho.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7e4c2a91f38'
down_revision = 'f5b57613d924'
branch_labels = None
depends_on = None


# Vendor dropdown ke purane 5 options — yahi seed karenge (VT-0001 ... VT-0005)
VENDOR_TYPES = [
    "Raw Material Supplier",
    "Job Worker / Sub-contractor",
    "Transporter",
    "Service Provider",
    "Other",
]

vendor_types_table = sa.table(
    "vendor_types",
    sa.column("id", sa.Integer),
    sa.column("code", sa.String),
    sa.column("name", sa.String),
    sa.column("is_active", sa.Boolean),
    sa.column("is_deleted", sa.Boolean),
)


def upgrade():
    op.create_table(
        'vendor_types',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_vendor_types')),
        sa.UniqueConstraint('code', name=op.f('uq_vendor_types_vendor_types_code')),
    )

    # Safety: table me pehle se data ho to dobara insert mat karo
    conn = op.get_bind()
    existing = conn.execute(sa.text("SELECT COUNT(*) FROM vendor_types")).scalar()
    if existing:
        return

    op.bulk_insert(
        vendor_types_table,
        [
            {
                "id": i,
                "code": f"VT-{i:04d}",
                "name": name,
                "is_active": True,
                "is_deleted": False,
            }
            for i, name in enumerate(VENDOR_TYPES, start=1)
        ],
    )


def downgrade():
    op.drop_table('vendor_types')
