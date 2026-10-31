# Wire Drawing ko 3 alag Work Stages me todta hai: Wire Drawing 1 / 2 / 3 (client change #8d: "3 machines ek line me", 12 mm -> 3 -> 1 -> 0.8 mm).
#   python split_wire_drawing.py <erp.db path>
# Kyun alag stages: routing me stage ek ke baad ek chalte hain, to teeno pass ek-ek karke aate hain aur har pass ka scrap / operator alag likha jaata hai.
# Pehle ek stage me 2 machines thi jo scheduler me parallel ginti thi — woh galat tha. Koi code badalna nahi, sirf master data.
# Kya karta hai: (1) purane "Wire Drawing" ka naam "Wire Drawing 1"; (2) "Wire Drawing 2" aur "3" naye stages (sort order +1, +2);
# (3) har stage ko apni ek machine (purani doosri machine stage 2 me jaati hai, 3rd nayi banti hai — capacity ANDAZE hai, plant se confirm karni hai);
# (4) jis product ke routing me Wire Drawing hai usme 2 aur 3 bhi jud jaate hain. Purane production orders ka snapshot nahi badalta.
# Kuch delete nahi hota. Dobara chalane par bhi safe (idempotent).
import sqlite3
import sys

c = sqlite3.connect(sys.argv[1])
c.execute("pragma foreign_keys=on")


def next_code(table, prefix):
    rows = c.execute(f"select code from {table}").fetchall()
    nums = [int(r[0].split("-")[1]) for r in rows if r[0].startswith(prefix + "-") and r[0].split("-")[1].isdigit()]
    return f"{prefix}-{(max(nums) if nums else 0) + 1:04d}"


stage1 = c.execute("select id, sort_order from work_stage where name = 'Wire Drawing 1' and is_deleted = 0").fetchone()
if stage1 is None:
    old = c.execute("select id, sort_order from work_stage where name = 'Wire Drawing' and is_deleted = 0").fetchone()
    if old is None:
        sys.exit("No 'Wire Drawing' work stage found. Nothing to do.")
    stage1 = old
    c.execute("update work_stage set name = 'Wire Drawing 1' where id = ?", (old[0],))

stage_ids = [stage1[0]]
for n in (2, 3):
    row = c.execute("select id from work_stage where name = ? and is_deleted = 0", (f"Wire Drawing {n}",)).fetchone()
    if row is None:
        c.execute("insert into work_stage (code, name, sort_order, is_active, is_deleted, is_batch, requires_lab_qc, scrap_after_next, created_at) "
                  "values (?, ?, ?, 1, 0, 0, 0, 0, datetime('now'))", (next_code("work_stage", "WS"), f"Wire Drawing {n}", stage1[1] + n - 1))
        row = c.execute("select id from work_stage where name = ?", (f"Wire Drawing {n}",)).fetchone()
    stage_ids.append(row[0])

# Machines: stage 1 ki machines se pehli stage 1 me, doosri stage 2 me; jahan machine nahi wahan nayi (pehli machine ki capacity ki copy)
machines = c.execute("select id, name, capacity, capacity_per_hour, capacity_unit_id, hours_per_day, line_id from machines "
                     "where work_stage_id = ? and is_deleted = 0 order by id", (stage_ids[0],)).fetchall()
if not machines:
    sys.exit("No machine found on Wire Drawing 1 to copy the capacity from. Add a machine first.")
for k in (0, 1, 2):
    have = c.execute("select count(*) from machines where work_stage_id = ? and is_deleted = 0", (stage_ids[k],)).fetchone()[0]
    if have:
        continue
    if k < len(machines):
        mid = machines[k][0]
        c.execute("update machines set work_stage_id = ? where id = ?", (stage_ids[k], mid))
    else:
        base = machines[0]
        c.execute("insert into machines (code, name, work_stage_id, capacity, capacity_per_hour, capacity_unit_id, hours_per_day, line_id, status, is_deleted, created_at) "
                  "values (?, ?, ?, ?, ?, ?, ?, ?, 'active', 0, datetime('now'))",
                  (next_code("machines", "MC"), "Wire Drawing Machine", stage_ids[k], base[2], base[3], base[4], base[5], base[6]))
        mid = c.execute("select max(id) from machines").fetchone()[0]
    c.execute("update machines set name = ? where id = ?", (f"Wire Drawing Machine {k + 1}", mid))

# Product routing: jin products me Wire Drawing 1 hai unme 2 aur 3 bhi
added = 0
for (product_id,) in c.execute("select product_id from product_routing_stages where work_stage_id = ?", (stage_ids[0],)).fetchall():
    for sid in stage_ids[1:]:
        if not c.execute("select 1 from product_routing_stages where product_id = ? and work_stage_id = ?", (product_id, sid)).fetchone():
            c.execute("insert into product_routing_stages (product_id, work_stage_id, created_at) values (?, ?, datetime('now'))", (product_id, sid))
            added += 1
c.commit()
print("Wire Drawing stages:", stage_ids, "| routing rows added:", added)
for row in c.execute("select w.name, w.sort_order, m.code, m.name, m.capacity_per_hour from work_stage w left join machines m on m.work_stage_id = w.id and m.is_deleted = 0 "
                     "where w.name like 'Wire Drawing%' and w.is_deleted = 0 order by w.sort_order"):
    print("  ", row)
