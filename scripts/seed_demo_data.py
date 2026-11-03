# Demo ke liye master data theek karta hai: 2 Production Lines (har line ke paas poore stages ki apni machines), Racks, aur sab ko jodta hai.
#   python seed_demo_data.py <erp.db path>
# Kya karta hai:
#   1. Work Stages: Melting & Alloying par Batch + Lab QC + "Scrap later" flag (client change 6, 7, 8).
#   2. Recipe lines ko stage se jodta hai (Tin, Lead -> Melting & Alloying; flux -> Flux Preparation).
#   3. Wire Drawing ko 3 stages me todta hai (scripts/split_wire_drawing.py chalakar).
#   4. Har stage ki 2 machines (ek Line 1, ek Line 2): jo hai use jodta hai, jo kam hai wo nayi banata hai (capacity pehli machine ki copy).
#   5. Line 1 aur Line 2 banata hai (daily capacity KG/din, handler) aur machines unse jodta hai.
#   6. Racks: RM warehouse me A, B, C; FG warehouse me 1, 2, 3. Maujooda GRN lines (material ke hisaab se) aur FG batch ko rack deta hai.
#   7. Product ka min / max stock (finished goods alert ke liye).
#   8. Vendors ka lead time (15 / 18 / 20 din, ANDAZA) jahan khaali hai — Material plan ke liye.
# Kuch delete nahi hota. Dobara chalane par bhi safe (idempotent). Chalane se pehle DB ka backup lo.
import os
import sqlite3
import subprocess
import sys

DB = sys.argv[1]
HERE = os.path.dirname(os.path.abspath(__file__))

# Pehle Wire Drawing split (alag script, wo khud idempotent hai)
subprocess.run([sys.executable, os.path.join(HERE, "split_wire_drawing.py"), DB], check=True)

c = sqlite3.connect(DB)
c.execute("pragma foreign_keys=on")


def next_code(table, prefix):
    rows = c.execute(f"select code from {table}").fetchall()
    nums = [int(r[0].split("-")[1]) for r in rows if r[0].startswith(prefix + "-") and r[0].split("-")[1].isdigit()]
    return f"{prefix}-{(max(nums) if nums else 0) + 1:04d}"


def stage_id(name):
    row = c.execute("select id from work_stage where name = ? and is_deleted = 0 and is_active = 1", (name,)).fetchone()
    if row is None:
        sys.exit(f"Work stage '{name}' not found.")
    return row[0]


# ---- 1. Melting & Alloying ke flags ----
melting = stage_id("Melting & Alloying")
c.execute("update work_stage set is_batch = 1, requires_lab_qc = 1, scrap_after_next = 1 where id = ?", (melting,))

# ---- 2. Recipe lines -> stage (sirf jahan abhi khaali hai) ----
flux_stage = stage_id("Flux Preparation")
c.execute("update variant_recipe_items set work_stage_id = ? where work_stage_id is null and is_flux = 1", (flux_stage,))
c.execute("update variant_recipe_items set work_stage_id = ? where work_stage_id is null and is_flux = 0", (melting,))

# ---- 3 + 4. Har stage ki 2 machines: [Line 1 ki, Line 2 ki] ----
MACHINES = {
    "Flux Preparation": ["Flux Mixer 1", "Flux Mixer 2"],
    "Melting & Alloying": ["Melting Furnace 1", "Melting Furnace 2"],
    "Ingot Casting": ["Ingot Casting Machine 1", "Ingot Casting Machine 2"],
    "Extrusion": ["Extrusion Press 1", "Extrusion Press 2"],
    "Wire Drawing 1": ["Wire Drawing Machine 1", "Wire Drawing Machine 4"],
    "Wire Drawing 2": ["Wire Drawing Machine 2", "Wire Drawing Machine 5"],
    "Wire Drawing 3": ["Wire Drawing Machine 3", "Wire Drawing Machine 6"],
    "Spooling": ["Spooling Machine 1", "Spooling Machine 2"],
    "Testing & QC": ["Testing Bench 1", "Testing Bench 2"],
    "Packing": ["Packing Table 1", "Packing Table 2"],
}

# ---- 5. Lines (pehle bana lo taaki machine unse jud sake) ----
LINES = [("Line 1", 600, "Ramesh Patel"), ("Line 2", 500, "Kiran Shah")]
line_ids = []
for name, capacity, handler in LINES:
    row = c.execute("select id from production_lines where name = ? and is_deleted = 0", (name,)).fetchone()
    if row is None:
        last = c.execute("select max(id) from production_lines").fetchone()[0] or 0
        c.execute("insert into production_lines (code, name, daily_capacity_kg, handler, is_active, is_deleted, created_at) values (?, ?, ?, ?, 1, 0, datetime('now'))",
                  (f"LN-{last + 1:04d}", name, capacity, handler))
        row = c.execute("select id from production_lines where name = ? and is_deleted = 0", (name,)).fetchone()
    line_ids.append(row[0])

created = 0
for stage_name, names in MACHINES.items():
    sid = stage_id(stage_name)
    for slot, machine_name in enumerate(names):
        have = c.execute("select id from machines where name = ? and work_stage_id = ? and is_deleted = 0", (machine_name, sid)).fetchone()
        if have is None:
            # Is stage ki koi machine jo kisi slot ke naam par nahi hai (jaise purani "Wire Drawing Machine") use rename karke slot me lo
            spare = c.execute("select id from machines where work_stage_id = ? and is_deleted = 0 and name not in (%s) order by id limit 1"
                              % ",".join("?" * len(names)), (sid, *names)).fetchone()
            if spare is not None:
                c.execute("update machines set name = ? where id = ?", (machine_name, spare[0]))
                have = spare
        if have is None:
            base = c.execute("select capacity, capacity_per_hour, capacity_unit_id, hours_per_day from machines where work_stage_id = ? and is_deleted = 0 order by id limit 1", (sid,)).fetchone()
            c.execute("insert into machines (code, name, work_stage_id, capacity, capacity_per_hour, capacity_unit_id, hours_per_day, line_id, status, is_deleted, created_at) "
                      "values (?, ?, ?, ?, ?, ?, ?, ?, 'active', 0, datetime('now'))",
                      (next_code("machines", "MC"), machine_name, sid, base[0], base[1], base[2], base[3], line_ids[slot]))
            created += 1
        else:
            c.execute("update machines set line_id = ? where id = ?", (line_ids[slot], have[0]))

# ---- 6. Racks ----
def warehouse_id(wtype):
    row = c.execute("select id from warehouses where warehouse_type = ? and is_active = 1 and is_deleted = 0 order by id limit 1", (wtype,)).fetchone()
    return row[0] if row else None


def rack(warehouse, name):
    row = c.execute("select id from racks where warehouse_id = ? and lower(name) = lower(?) and is_deleted = 0", (warehouse, name)).fetchone()
    if row is None:
        c.execute("insert into racks (code, name, warehouse_id, is_active, is_deleted, created_at) values (?, ?, ?, 1, 0, datetime('now'))",
                  (next_code("racks", "RK"), name, warehouse))
        row = c.execute("select id from racks where warehouse_id = ? and lower(name) = lower(?) and is_deleted = 0", (warehouse, name)).fetchone()
    return row[0]


rm_wh, fg_wh = warehouse_id("RM"), warehouse_id("FG")
rm_racks = {n: rack(rm_wh, n) for n in ("A", "B", "C")}
fg_racks = {n: rack(fg_wh, n) for n in ("1", "2", "3")}

# Maujooda GRN lines: Lead / Tin jaisi metal A me, flux-chemical B me, spool / packing C me (sirf jahan rack abhi khaali hai)
RACK_BY_MATERIAL = {"RM-0001": "A", "RM-0006": "A", "RM-0011": "B", "RM-0012": "B", "RM-0008": "C", "RM-0009": "C", "RM-0005": "C", "RM-0007": "C", "RM-0004": "C"}
for line_id, code in c.execute("select g.id, r.code from grn_lines g join purchase_order_lines p on p.id = g.po_line_id join raw_materials r on r.id = p.raw_material_id where g.rack_id is null").fetchall():
    if code in RACK_BY_MATERIAL:
        c.execute("update grn_lines set rack_id = ? where id = ?", (rm_racks[RACK_BY_MATERIAL[code]], line_id))
# FG batch (sirf Good, Scrap nahi) -> rack 1
c.execute("update fg_batches set rack_id = ? where rack_id is null and kind = 'FG'", (fg_racks["1"],))

# ---- 7. Product min / max stock (sirf jahan khaali hai) ----
c.execute("update products set min_stock = 50, max_stock = 1000 where min_stock is null and max_stock is null and is_deleted = 0")

# ---- 8. Vendor lead time (din): Material plan "PO kab tak dalo" ke liye. Spec: 15-20 din. Sirf jahan khaali hai; ANDAZA hai, vendor se confirm karna ----
for index, (vendor_id,) in enumerate(c.execute("select id from vendors where lead_time_days is null and is_deleted = 0 order by id").fetchall()):
    c.execute("update vendors set lead_time_days = ? where id = ?", ((15, 18, 20)[index % 3], vendor_id))

c.commit()

print("Lines:")
for row in c.execute("select l.code, l.name, l.daily_capacity_kg, l.handler, count(m.id) from production_lines l left join machines m on m.line_id = l.id and m.is_deleted = 0 where l.is_deleted = 0 group by l.id"):
    print("  ", row)
print("Machines (new created: %d):" % created)
for row in c.execute("select w.sort_order, w.name, m.code, m.name, l.name, m.capacity_per_hour from machines m join work_stage w on w.id = m.work_stage_id left join production_lines l on l.id = m.line_id "
                     "where m.is_deleted = 0 and w.is_deleted = 0 and w.is_active = 1 order by w.sort_order, w.id, m.id"):
    print("  ", row)
print("Racks:")
for row in c.execute("select r.code, r.name, w.name from racks r join warehouses w on w.id = r.warehouse_id where r.is_deleted = 0 order by r.id"):
    print("  ", row)
print("GRN lines with rack:", c.execute("select count(*) from grn_lines where rack_id is not null").fetchone()[0], "| FG batches with rack:", c.execute("select count(*) from fg_batches where rack_id is not null").fetchone()[0])
