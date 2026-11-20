"""fix_list 5: har work stage me scrap record ho sake (Extrusion / Wire Drawing ka "No scrap" tick hata)

Revision ID: a1e6c3d8f2b7
Revises: f8c3e0a4b6d5
Create Date: 2026-11-20 20:00:00.000000

"""
from alembic import op


revision = 'a1e6c3d8f2b7'
down_revision = 'f8c3e0a4b6d5'
branch_labels = None
depends_on = None


def upgrade():
    # Data change: pehle Extrusion / Wire Drawing par "No scrap" tick tha. Ab master me tick seedha hai ("Scrap can be recorded at this stage",
    # default on), isliye saare stages par scrap allowed kar do. Jise sach me band karna ho wo master me tick hata sakta hai.
    op.execute("UPDATE work_stage SET no_scrap = 0")


def downgrade():
    # Purani values wapas nahi aati (kaun sa stage tha, yaad nahi); schema same rehta hai
    pass
