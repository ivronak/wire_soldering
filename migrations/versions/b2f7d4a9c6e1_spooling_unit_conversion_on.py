"""fix_list 2: Spooling = unit conversion stage (KG -> PCS), master me ON (pehle 0 tha, isliye Testing/Packing KG me chal rahe the)

Revision ID: b2f7d4a9c6e1
Revises: a1e6c3d8f2b7
Create Date: 2026-11-20 21:00:00.000000

"""
from alembic import op


revision = 'b2f7d4a9c6e1'
down_revision = 'a1e6c3d8f2b7'
branch_labels = None
depends_on = None


def upgrade():
    # One-time data fix: Spooling me unit badalta hai (wire KG aata hai, spool PCS nikalte hain), isliye uska "Unit conversion stage" tick ON hona hi chahiye.
    # Code me koi naam hardcode nahi: ye sirf maujooda data theek karta hai; aage naya aisa stage master me tick karke bana sakte hain.
    # Sirf PCS wale product par asar padta hai (KG wale product jaise pehle chalte hain).
    op.execute("UPDATE work_stage SET counts_pcs = 1 WHERE lower(name) = 'spooling' AND is_deleted = 0")


def downgrade():
    # Pehle ye 0 tha; wapas 0 kar dena theek hai
    op.execute("UPDATE work_stage SET counts_pcs = 0 WHERE lower(name) = 'spooling'")
