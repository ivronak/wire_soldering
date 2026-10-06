"""seed indian states with gst codes

Revision ID: fd2c563b95f7
Revises: ccde7d8289e6
Create Date: 2026-10-01 18:04:39.561405

State Master ko pehle se bhar deta hai - saare 36 states / union territories,
unke GST state code ke saath (Gujarat = 24, Delhi = 07, Maharashtra = 27 ...).

Kyun seed kar rahe hain:
- Ye naam + code government ka fixed data hai, kisi user ka banaya hua nahi.
- Vendor / Customer / Branch ke dropdowns (aage) isi table se aayenge, to
  table khaali ho to dropdown bhi khaali dikhta.
- `code` bhi ST-0001 se seed kar diya hai, taaki baad me
  `generate_next_state_code()` (last id + 1) se consistency bani rahe -
  agla naya state ST-0037 hi banega.

Seed ka order `app/constants.py` ke INDIAN_STATES jaisa hi rakha hai, taaki
purane text data (jaisa "Gujarat") mapping me seedha match ho jaaye.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fd2c563b95f7'
down_revision = 'ccde7d8289e6'
branch_labels = None
depends_on = None


# (naam, GST state code) - INDIAN_STATES ke order me hi
STATES = [
    ("Andaman and Nicobar Islands", "35"),
    ("Andhra Pradesh", "37"),
    ("Arunachal Pradesh", "12"),
    ("Assam", "18"),
    ("Bihar", "10"),
    ("Chandigarh", "04"),
    ("Chhattisgarh", "22"),
    ("Dadra and Nagar Haveli and Daman and Diu", "26"),
    ("Delhi", "07"),
    ("Goa", "30"),
    ("Gujarat", "24"),
    ("Haryana", "06"),
    ("Himachal Pradesh", "02"),
    ("Jammu and Kashmir", "01"),
    ("Jharkhand", "20"),
    ("Karnataka", "29"),
    ("Kerala", "32"),
    ("Ladakh", "38"),
    ("Lakshadweep", "31"),
    ("Madhya Pradesh", "23"),
    ("Maharashtra", "27"),
    ("Manipur", "14"),
    ("Meghalaya", "17"),
    ("Mizoram", "15"),
    ("Nagaland", "13"),
    ("Odisha", "21"),
    ("Puducherry", "34"),
    ("Punjab", "03"),
    ("Rajasthan", "08"),
    ("Sikkim", "11"),
    ("Tamil Nadu", "33"),
    ("Telangana", "36"),
    ("Tripura", "16"),
    ("Uttar Pradesh", "09"),
    ("Uttarakhand", "05"),
    ("West Bengal", "19"),
]


# bulk_insert ke liye halka sa table definition (model import nahi karte,
# kyunki migration purane schema pe bhi chalni chahiye)
states_table = sa.table(
    "states",
    sa.column("id", sa.Integer),
    sa.column("code", sa.String),
    sa.column("name", sa.String),
    sa.column("gst_state_code", sa.String),
    sa.column("is_active", sa.Boolean),
    sa.column("is_deleted", sa.Boolean),
)


def upgrade():
    conn = op.get_bind()

    # Safety: table me pehle se data ho to dobara insert mat karo
    existing = conn.execute(sa.text("SELECT COUNT(*) FROM states")).scalar()
    if existing:
        return

    op.bulk_insert(
        states_table,
        [
            {
                "id": i,
                "code": f"ST-{i:04d}",
                "name": name,
                "gst_state_code": gst_code,
                "is_active": True,
                "is_deleted": False,
            }
            for i, (name, gst_code) in enumerate(STATES, start=1)
        ],
    )


def downgrade():
    # Sirf wahi rows hatao jo isi seed se aayi thi
    codes = [f"ST-{i:04d}" for i in range(1, len(STATES) + 1)]
    op.get_bind().execute(
        sa.text("DELETE FROM states WHERE code IN :codes").bindparams(
            sa.bindparam("codes", expanding=True)
        ),
        {"codes": codes},
    )
