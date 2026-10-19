"""real soldering wire stages and machines

Data migration: master me wire-harness wale stages / machines (Cutting, Stripping, Crimping, Soldering Station...) the,
jo soldering wire ki asli banavat se mel nahi khate. Yahan flux-cored solder wire ki asli process ke stages aur machines daale
jaate hain. Purane rows delete nahi hote, sirf is_deleted = 1 (list se hat jaate hain, DB me bache rehte hain).

Capacity ke numbers ANDAZE hain (ek chhote solder wire plant ke hisaab se). Plant ki asli rated capacity se Machine master
me badal lena chahiye.

Revision ID: 08e8253c0c8a
Revises: da067ce77f7e
Create Date: 2026-10-19 11:14:28.211525

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '08e8253c0c8a'
down_revision = 'da067ce77f7e'
branch_labels = None
depends_on = None

# Flux-cored solder wire ki asli process (order me): flux banana -> pighla ke alloy -> ingot / billet dhalna ->
# extrusion (flux core ke saath moti wire) -> drawing (final mote-pan tak) -> spool par lapetna -> test -> packing
STAGES = [
    ("Flux Preparation", 10),
    ("Melting & Alloying", 20),
    ("Ingot Casting", 30),
    ("Extrusion", 40),
    ("Wire Drawing", 50),
    ("Spooling", 60),
    ("Testing & QC", 70),
    ("Packing", 80),
]

# (stage, machine, KG per hour)
MACHINES = [
    ("Flux Preparation", "Flux Mixer 1", 60),
    ("Melting & Alloying", "Melting Furnace 1", 150),
    ("Melting & Alloying", "Melting Furnace 2", 150),
    ("Ingot Casting", "Ingot Casting Machine 1", 200),
    ("Extrusion", "Extrusion Press 1", 120),
    ("Wire Drawing", "Wire Drawing Machine 1", 80),
    ("Wire Drawing", "Wire Drawing Machine 2", 80),
    ("Spooling", "Spooling Machine 1", 100),
    ("Spooling", "Spooling Machine 2", 100),
    ("Testing & QC", "Testing Bench 1", 200),
    ("Packing", "Packing Table 1", 120),
]

OLD_STAGE_NAMES = ["Cutting", "Stripping", "Crimping", "Soldering", "Assembly", "QC Inspection", "Packing"]
OLD_MACHINE_NAMES = ["Cutting Bench", "Wire Stripping Machine 1", "Crimping Press 1", "Soldering Station 1",
                     "Soldering Station 2 (Updated)", "Cutting 3"]


def upgrade():
    bind = op.get_bind()

    kg = bind.execute(sa.text("select id from units where upper(code) = 'KG' and is_deleted = 0 limit 1")).scalar()

    # 1) Purane (wire-harness) stages / machines list se hatao — pehle machines (stage par depend karti hain)
    for name in OLD_MACHINE_NAMES:
        bind.execute(sa.text("update machines set is_deleted = 1 where name = :n and is_deleted = 0"), {"n": name})
    # Purane "Packing" stage ko bhi hatao: neeche naya Packing sahi order me banta hai
    for name in OLD_STAGE_NAMES:
        bind.execute(sa.text("update work_stage set is_deleted = 1 where name = :n and is_deleted = 0"), {"n": name})

    # 2) Naye stages (agar is naam ka live stage pehle se nahi hai)
    stage_ids = {}
    for name, order in STAGES:
        found = bind.execute(sa.text("select id from work_stage where name = :n and is_deleted = 0"), {"n": name}).scalar()
        if found is None:
            last = bind.execute(sa.text("select coalesce(max(id), 0) from work_stage")).scalar()
            bind.execute(sa.text(
                "insert into work_stage (code, name, sort_order, is_active, is_deleted) values (:c, :n, :o, 1, 0)"),
                {"c": f"WS-{last + 1:04d}", "n": name, "o": order})
            found = bind.execute(sa.text("select id from work_stage where name = :n and is_deleted = 0"), {"n": name}).scalar()
        stage_ids[name] = found

    # 3) Naye machines (numeric capacity: KG per hour, 8 ghante / din)
    for stage_name, machine_name, per_hour in MACHINES:
        exists = bind.execute(sa.text("select id from machines where name = :n and is_deleted = 0"), {"n": machine_name}).scalar()
        if exists is not None:
            continue
        last = bind.execute(sa.text("select coalesce(max(id), 0) from machines")).scalar()
        bind.execute(sa.text(
            "insert into machines (code, name, work_stage_id, capacity, capacity_per_hour, capacity_unit_id, hours_per_day, status, is_deleted) "
            "values (:c, :n, :s, :t, :p, :u, 8, 'active', 0)"),
            {"c": f"MC-{last + 1:04d}", "n": machine_name, "s": stage_ids[stage_name], "t": f"{per_hour} KG/hr", "p": per_hour, "u": kg})


def downgrade():
    # Data migration hai: purane rows wapas live karna / naye hatana jaanbujhkar nahi kiya (kuch jagah ye rows use ho chuki ho sakti hain).
    pass
