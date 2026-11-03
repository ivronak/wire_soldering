# Live (portal) ERP me demo dikhane layak entries jodta hai. Kuch delete / overwrite nahi karta, sirf add karta hai.
#   venv/bin/python scripts/seed_demo_entries.py           (app ke folder se; app ki asli instance/erp.db par chalta hai)
# Pehle scripts/seed_demo_data.py (masters: lines, racks, stages, machines) aur flask db upgrade ho chuka hona chahiye.
# Kya karta hai (dobara chalane par safe — jo ho chuka use chhod deta hai):
#   1. Product Category "Soldering Wire" par flat icon.
#   2. Spool / Box wale RM ko "packing material" mark karta hai (is_packing) taaki Product ke Packing table me aayein.
#   3. 500g Spool wale product ko PCS me badalta hai: 1 spool = 0.5 KG (Spooling stage), 1 box = 25 KG (Packing stage).
#   4. Opening stock (Tin, Lead, Flux, spool, box) taaki demo order issue ho sake.
#   5. Ek poora PCS order (200 PCS x 0.5 KG): allowance + issue + stages + leftover return + output -> FG me spool / box ke saath.
#   6. Ek Draft order (queue / material plan dikhane ke liye).
# Sab kuch app ke apne routes se hota hai (test client), isliye stock / ledger ke rules wahi lagte hain.
import sys
from datetime import date, timedelta

from werkzeug.datastructures import MultiDict

from app import app
from app.extensions import db
from app.models import (Machines, OpeningStock, Product, ProductCategories, ProductionLine, ProductionOrder, ProductionOrderLine, ProductionOutput,
                        ProductPackingItem, Rack, RawMaterial, Unit, Warehouse, WorkStage)
from app.production_output.posting import leftover_rows

DEMO_TAG = "Demo: spool order"
QUEUE_TAG = "Demo: queued order"

ctx = app.app_context()
ctx.push()
print("Database:", db.engine.url)
client = app.test_client()
today = date.today()


def say(text):
    print(" -", text)


def flashes():
    with client.session_transaction() as sess:
        return [m for _cat, m in sess.pop("_flashes", [])]


def find_rm(name_part):
    return RawMaterial.query.filter(RawMaterial.is_deleted == False, RawMaterial.name.ilike(f"%{name_part}%")).order_by(RawMaterial.id).first()


# ---- 1. Category icon ----
category = ProductCategories.query.filter(ProductCategories.is_deleted == False, ProductCategories.name.ilike("%solder%")).first()
if category is not None and not category.icon:
    category.icon = "wire"
    say(f"Category '{category.name}' icon set")

# ---- 2. Packing materials ----
spool500, spool1k, carton = find_rm("500G Spool"), find_rm("1KG Spool"), find_rm("Corrugated Box")
for rm in (spool500, spool1k, carton):
    if rm is not None and not rm.is_packing:
        rm.is_packing = True
        say(f"{rm.code} {rm.name} marked as packing material")
db.session.commit()

# ---- 3. Product in PCS with spool + box ----
product = Product.query.filter(Product.is_deleted == False, Product.name.ilike("%500g spool%")).order_by(Product.id).first()
if product is None or spool500 is None or carton is None:
    sys.exit("Demo product / spool / box not found; nothing more to do.")
pcs = Unit.query.filter_by(code="PCS").first()
stage_spool = WorkStage.query.filter_by(name="Spooling", is_deleted=False, is_active=True).first()
stage_pack = WorkStage.query.filter_by(name="Packing", is_deleted=False, is_active=True).order_by(WorkStage.sort_order.desc()).first()
if not ProductPackingItem.query.filter_by(product_id=product.id).first():
    db.session.add(ProductPackingItem(product_id=product.id, raw_material_id=spool500.id, kg_per_pack=0.5, work_stage_id=stage_spool.id))
    db.session.add(ProductPackingItem(product_id=product.id, raw_material_id=carton.id, kg_per_pack=25, work_stage_id=stage_pack.id))
    product.base_unit_id = pcs.id
    say(f"{product.code} now in PCS: 1 spool per 0.5 KG (Spooling), 1 box per 25 KG (Packing)")
db.session.commit()

# ---- 4. Opening stock ----
store = Warehouse.query.filter_by(warehouse_type="RM", is_active=True, is_deleted=False).order_by(Warehouse.id).first()
tin, lead, flux = find_rm("Tin"), find_rm("Lead"), find_rm("Flux")
if not OpeningStock.query.filter(OpeningStock.remarks == "Demo stock").first():
    # Metal ka stock jaanbujh kar thoda: demo tour ka "Material plan" step tabhi dikhta hai jab bade order ka maal kam pade
    rows = [(tin, 150, 1000), (lead, 80, 220), (flux, 8, 400), (spool500, 2000, 12), (spool1k, 500, 18), (carton, 200, 45)]
    data = {"as_of_date": today.isoformat(), "warehouse_id": store.id, "remarks": "Demo stock"}
    for i, (rm, qty, cost) in enumerate(rows):
        data.update({f"material_id_{i}": rm.id, f"qty_{i}": qty, f"cost_{i}": cost, f"batch_{i}": f"DEMO-{rm.code}"})
    client.post("/opening_stock/add", data=data)
    sheet = OpeningStock.query.filter(OpeningStock.remarks == "Demo stock").first()
    if sheet is not None and sheet.status == "Draft":
        client.post(f"/opening_stock/post/{sheet.id}")
        sheet = OpeningStock.query.filter(OpeningStock.remarks == "Demo stock").first()
    say("Opening stock: " + (sheet.status if sheet else "NOT SAVED " + str(flashes())))
    if sheet is None:
        sys.exit("Opening stock could not be saved.")


# ---- 5 + 6. Orders (app ke routes se) ----
def order_form(qty, remarks, line, spare):
    # Order form jaisa hi: product, qty, kg per PCS, line, har routing stage ki us line ki machines, har RM ka spare %
    data = [("order_date", today.isoformat()), ("product_id", str(product.id)), ("planned_qty", str(qty)), ("unit_weight", "0.5"),
            ("start_date", today.isoformat()), ("remarks", remarks), ("line_id", str(line.id))]
    for row in product.routing_stages:
        machines = Machines.query.filter_by(work_stage_id=row.work_stage_id, is_deleted=False, status="active", line_id=line.id).all()
        data += [(f"machines_{row.work_stage_id}", str(m.id)) for m in machines]
    data += [(f"allowance_rm_{rm.id}", str(pct)) for rm, pct in spare]
    return MultiDict(data)


line1, line2 = ProductionLine.query.filter_by(is_deleted=False, is_active=True).order_by(ProductionLine.id).limit(2).all()
spare = [(tin, 1), (lead, 1), (flux, 5)]

done_order = ProductionOrder.query.filter_by(remarks=DEMO_TAG, is_deleted=False).first()
if done_order is None:
    client.post("/production_orders/add", data=order_form(200, DEMO_TAG, line1, spare))
    done_order = ProductionOrder.query.filter_by(remarks=DEMO_TAG, is_deleted=False).first()
    if done_order is None:
        sys.exit("Demo order could not be created: " + str(flashes()))
    say(f"Order {done_order.prod_no} created (200 PCS x 0.5 KG)")
    client.post(f"/production_orders/release/{done_order.id}")
    db.session.expire_all()
    done_order = db.session.get(ProductionOrder, done_order.id)
    # Material: needed + spare (spare baad me wapas aayega)
    issue = [("production_order_id", str(done_order.id)), ("issue_date", today.isoformat()), ("issue_action", "post")]
    for i, line in enumerate(done_order.lines):
        issue += [(f"line_id_{i}", str(line.id)), (f"qty_{i}", str(round(line.remaining_qty + line.allowance_remaining_qty, 4)))]
    client.post("/material_issues/add", data=MultiDict(issue))
    # Line ki capacity se chhota batch ho to start par wajah likhni padti hai (Line capacity rule)
    client.post(f"/production_orders/start/{done_order.id}", data={"under_reason": "Small demo batch"})
    db.session.expire_all()
    done_order = db.session.get(ProductionOrder, done_order.id)
    say(f"{done_order.prod_no}: material issued, status {done_order.status}")
    if done_order.status != "In production":
        sys.exit("Demo order did not start: " + str(flashes()))
    # Saare stage (lab QC wale me nakli TC ke saath): demo shortcut
    client.post(f"/tour/finish_stages/{done_order.id}")
    db.session.expire_all()
    done_order = db.session.get(ProductionOrder, done_order.id)
    for stage, operator in zip(done_order.stages, ("Meena Shah", "Ramesh Patel", "Kiran Shah")):
        stage.operator = operator
    # Stage me asli use (jo routing Complete form likhta): metal / flux = jitna chahiye tha, spool / box = output KG / kg per pack
    batch_kg = done_order.planned_qty * done_order.unit_weight
    for line in done_order.lines:
        wanted = float(int(batch_kg / line.kg_per_pack + 1e-9)) if line.is_packing else line.required_qty
        line.used_qty = min(wanted, line.issued_qty)
    db.session.commit()
    # Bacha hua (spare) store me wapas — Output se pehle zaroori
    back = [("production_order_id", str(done_order.id)), ("return_date", today.isoformat()), ("reason", "Unused spare (allowance)")]
    i = 0
    for order_line, extra in leftover_rows(done_order):
        left = extra
        for issue_doc in sorted(done_order.issues, key=lambda d: d.id):
            for il in issue_doc.lines:
                if il.production_order_line_id == order_line.id and il.returnable_qty > 0 and left > 0:
                    take = min(il.returnable_qty, left)
                    back += [(f"issue_line_id_{i}", str(il.id)), (f"qty_{i}", str(round(take, 4)))]
                    i += 1
                    left = round(left - take, 4)
    if i:
        client.post("/material_issues/return", data=MultiDict(back))
    db.session.expire_all()
    done_order = db.session.get(ProductionOrder, done_order.id)
    say(f"Unused spare returned to store ({i} lots); leftover now: {leftover_rows(done_order)}")
    # Output: Good = Spooling me gine hue spool (PCS)
    spools = next(l.used_qty for l in done_order.lines if l.is_packing and l.raw_material.base_unit_id == pcs.id)
    fg_rack = Rack.query.filter(Rack.is_deleted == False, Rack.is_active == True, Rack.warehouse.has(warehouse_type="FG")).order_by(Rack.id).first()
    client.post("/production_output/add", data={"production_order_id": done_order.id, "output_date": today.isoformat(), "good_qty": str(spools),
                                                "scrap_qty": "0", "recorded_by": "Meena Shah", "rack_id": fg_rack.id if fg_rack else ""})
    out = ProductionOutput.query.filter_by(production_order_id=done_order.id, status="Posted").first()
    say("Output: " + (f"{out.output_no} {out.good_qty:g} PCS in FG" if out else "NOT POSTED " + str(flashes())))

if not ProductionOrder.query.filter_by(remarks=QUEUE_TAG, is_deleted=False).first():
    client.post("/production_orders/add", data=order_form(1000, QUEUE_TAG, line2, spare))
    queued = ProductionOrder.query.filter_by(remarks=QUEUE_TAG, is_deleted=False).first()
    say("Queued order: " + (queued.prod_no if queued else "NOT CREATED " + str(flashes())))

db.session.commit()
print("Done.")
