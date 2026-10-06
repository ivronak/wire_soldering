"""payment term master

Revision ID: a3f1c7e92b40
Revises: d4e6f8a0b2c3
Create Date: 2026-10-02 06:20:00.000000

Payment Terms dropdown ka apna master banaya. Pehle ye Vendor / Customer /
Purchase order — teeno forms me hardcoded tha (5 options). Ab ye table hai,
aur wahi 5 options yahan seed kar diye taaki Step 1 me backfill clean ho.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3f1c7e92b40'
down_revision = 'd4e6f8a0b2c3'
branch_labels = None
depends_on = None


# Purane 5 options — jo Vendor / Customer / PO forms me hardcoded the.
# Yahi seed karenge (PT-0001 ... PT-0005).
PAYMENT_TERMS = [
    "Advance",
    "Net 15",
    "Net 30",
    "Net 45",
    "Net 60",
]

payment_terms_table = sa.table(
    "payment_terms",
    sa.column("id", sa.Integer),
    sa.column("code", sa.String),
    sa.column("name", sa.String),
    sa.column("is_active", sa.Boolean),
    sa.column("is_deleted", sa.Boolean),
)


def upgrade():
    op.create_table(
        'payment_terms',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_payment_terms')),
        sa.UniqueConstraint('code', name=op.f('uq_payment_terms_payment_terms_code')),
    )

    # Safety: table me pehle se data ho to dobara insert mat karo
    conn = op.get_bind()
    existing = conn.execute(sa.text("SELECT COUNT(*) FROM payment_terms")).scalar()
    if existing:
        return

    op.bulk_insert(
        payment_terms_table,
        [
            {
                "id": i,
                "code": f"PT-{i:04d}",
                "name": name,
                "is_active": True,
                "is_deleted": False,
            }
            for i, name in enumerate(PAYMENT_TERMS, start=1)
        ],
    )


def downgrade():
    op.drop_table('payment_terms')
