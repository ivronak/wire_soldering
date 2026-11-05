# MOCK DATA sirf UI / UX dekhne ke liye (local dev DB). Production orders ke har state ka namuna banata hai:
# running (progress bar), stock OK, late, PO coming, need to buy, plan-less, cancelled.
# Chalane se pehle DB ka backup leta hai: instance/erp.db.before-mock. Hatane ke liye:  python scripts/mock_production_orders.py remove
# (remove = backup wapas copy karta hai, isliye mock ke baad ka asli kaam wapas jaa sakta hai — pehle dhyan se sochna.)
# LIVE (server) par kabhi mat chalana.
import os
import shutil
import sys
from datetime import date, timedelta

from werkzeug.datastructures import MultiDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
DB = os.path.join(ROOT, "instance", "erp.db")
BACKUP = DB + ".before-mock"

if len(sys.argv) > 1 and sys.argv[1] == "remove":
    if not os.path.exists(BACKUP):
        sys.exit("No backup found (instance/erp.db.before-mock). Nothing to restore.")
    shutil.copyfile(BACKUP, DB)
    os.remove(BACKUP)
    print("Restored the database from the backup. Mock data is gone.")
    sys.exit(0)

if os.path.exists(BACKUP):
    sys.exit("A mock backup already exists. Run 'remove' first, or delete instance/erp.db.before-mock if you want to keep the current data.")
shutil.copyfile(DB, BACKUP)

from app import app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import *  # noqa: E402,F401,F403
from app.production_orders.scheduler import persist_schedule  # noqa: E402

MOCK = "MOCK DATA - for UI check"
today = date.today()

with app.app_context():
    c = app.test_client()
    store = Warehouse.query.filter_by(warehouse_type="RM", is_deleted=False).order_by(Warehouse.id).first()
    tin = RawMaterial.query.filter_by(code="RM-0001").first()
    lead = RawMaterial.query.filter_by(code="RM-0006").first()
    flux = RawMaterial.query.filter_by(code="RM-0011").first()
    product = Product.query.filter_by(is_deleted=False).first()
    assert store and tin and lead and flux and product, "Expected master data (RM-0001 / RM-0006 / RM-0011, a product) not found"

    # 1. Mock store stock (opening stock) taaki kuch orders "Stock OK" dikhein aur baaki short
    c.post("/opening_stock/add", data={"as_of_date": today.isoformat(), "warehouse_id": store.id, "remarks": MOCK,
                                       "material_id_0": tin.id, "qty_0": "700", "cost_0": "1000", "batch_0": "MOCK-T",
                                       "material_id_1": lead.id, "qty_1": "350", "cost_1": "220", "batch_1": "MOCK-L",
                                       "material_id_2": flux.id, "qty_2": "25", "cost_2": "400", "batch_2": "MOCK-F"})
    sheet = OpeningStock.query.order_by(OpeningStock.id.desc()).first()
    if sheet and sheet.status == "Draft":
        c.post(f"/opening_stock/post/{sheet.id}")

    stages = sorted(product.routing_stages, key=lambda r: (r.work_stage.sort_order, r.work_stage.id))
    all_machines = {r.work_stage_id: [m.id for m in Machines.query.filter_by(work_stage_id=r.work_stage_id, is_deleted=False, status="active")] for r in stages}
    one_machine = {sid: ids[:1] for sid, ids in all_machines.items()}

    def new_order(qty, machines=None, needed_by=None, remarks=MOCK):
        data = [("order_date", today.isoformat()), ("product_id", str(product.id)), ("planned_qty", str(qty)), ("unit_weight", "1"),
                ("start_date", today.isoformat()), ("remarks", remarks)]
        if needed_by:
            data.append(("needed_by", needed_by.isoformat()))
        for sid, ids in (machines or all_machines).items():
            data += [(f"machines_{sid}", str(i)) for i in ids]
        c.post("/production_orders/add", data=MultiDict(data))
        db.session.expire_all()
        return ProductionOrder.query.order_by(ProductionOrder.id.desc()).first()

    # 2. A: chal raha order (material issue + start, phir 2 din pehle shuru dikhane ke liye dates peeche)
    a = new_order(300, remarks=MOCK + " - running")
    c.post(f"/production_orders/release/{a.id}")
    db.session.expire_all()
    a = db.session.get(ProductionOrder, a.id)
    issue = [("production_order_id", str(a.id)), ("issue_date", today.isoformat()), ("issue_action", "post")]
    for i, line in enumerate(a.lines):
        issue += [(f"line_id_{i}", str(line.id)), (f"qty_{i}", str(line.required_qty))]
    c.post("/material_issues/add", data=MultiDict(issue))
    c.post(f"/production_orders/start/{a.id}")
    db.session.expire_all()
    a = db.session.get(ProductionOrder, a.id)
    if a.status == "In production":
        shift = timedelta(days=2)
        a.started_date = today - shift
        for st in a.stages:
            st.start_date -= shift
            st.end_date -= shift
        a.planned_start_date -= shift
        a.planned_end_date -= shift
        db.session.commit()

    # 2b. A me se thoda material production se wapas store me (Material return dikhane ke liye)
    db.session.expire_all()
    issue_lines = [l for i in MaterialIssue.query.filter_by(production_order_id=a.id, status="Posted").all() for l in i.lines]
    back = [(l, q) for l, q in zip(issue_lines[:2], (10, 5))]
    if back:
        data = [("production_order_id", str(a.id)), ("return_date", today.isoformat()), ("reason", "Not needed (excess)"), ("returned_by", "Production")]
        for idx, (l, q) in enumerate(back):
            data += [(f"issue_line_id_{idx}", str(l.id)), (f"qty_{idx}", str(q))]
        c.post("/material_issues/return", data=MultiDict(data))

    # 2c. A ke routing stages: pehle 2 poore, teesra chal raha (Routing tracker dikhane ke liye)
    from app.production_orders.scheduler import now_ist
    db.session.expire_all()
    a = db.session.get(ProductionOrder, a.id)
    if a.status == "In production" and a.stages:
        fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M")
        t = now_ist().replace(second=0, microsecond=0) - timedelta(days=2, hours=2)
        qty = 300.0
        for idx, (operator, hours, scrap) in enumerate((("Amit Desai", 5.5, 4.0), ("Ravi Patel", 1.5, 2.0), ("Meena Shah", None, None))):
            stage = db.session.get(ProductionOrder, a.id).stages[idx]
            c.post(f"/routing/start/{stage.id}", data={"operator": operator, "started_at": fmt(t)})
            if hours is None:
                break
            t = t + timedelta(hours=hours)
            qty = round(qty - scrap, 2)
            form = MultiDict([("completed_at", fmt(t)), ("qty_out", str(qty)), ("scrap_qty", str(scrap)), ("operator", operator), ("scrap_type_id", str(ScrapType.query.order_by(ScrapType.id).first().id)), ("scrap_kind", "Saleable")])
            for m in stage.machines:
                form.add("machine_ids", str(m.machine_id))
            c.post(f"/routing/complete/{stage.id}", data=form)
            db.session.expire_all()
            t = t + timedelta(minutes=25)

    # 3. B: released, stock OK, aaram se time par
    b = new_order(200, needed_by=today + timedelta(days=9), remarks=MOCK + " - stock OK")
    c.post(f"/production_orders/release/{b.id}")
    # 4. C: draft, ek-ek machine (lamba time), needed-by jaldi => Late
    c_order = new_order(500, machines=one_machine, needed_by=today + timedelta(days=3), remarks=MOCK + " - late")
    # 5. D: draft, thoda kam material, PO aa raha
    d = new_order(520, needed_by=today + timedelta(days=25), remarks=MOCK + " - PO coming")
    # 6. E: bada order, material kharidna padega
    e = new_order(800, remarks=MOCK + " - need to buy")
    # 7. F: plan nahi (stages hata do)
    f = new_order(100, remarks=MOCK + " - no plan")
    for st in list(f.stages):
        for m in list(st.machines):
            db.session.delete(m)
        db.session.delete(st)
    db.session.commit()
    # 8. G: cancelled
    g = new_order(150, remarks=MOCK + " - cancelled")
    c.post(f"/production_orders/cancel/{g.id}", data={"reason": "Customer postponed the order"})

    # 9. H aur I: poore stages ho chuke orders. H = "Record output" ke liye taiyaar, I = output record ho chuka (Finished goods dikhane ke liye)
    def run_to_end(qty, remarks):
        o = new_order(qty, remarks=remarks)
        c.post(f"/production_orders/release/{o.id}")
        db.session.expire_all()
        o = db.session.get(ProductionOrder, o.id)
        form = [("production_order_id", str(o.id)), ("issue_date", today.isoformat()), ("issue_action", "post")]
        for i, line in enumerate(o.lines):
            form += [(f"line_id_{i}", str(line.id)), (f"qty_{i}", str(line.required_qty))]
        c.post("/material_issues/add", data=MultiDict(form))
        c.post(f"/production_orders/start/{o.id}")
        db.session.expire_all()
        o = db.session.get(ProductionOrder, o.id)
        t = now_ist().replace(second=0, microsecond=0) - timedelta(hours=30)
        left = qty * o.unit_weight
        for idx in range(len(o.stages)):
            stage = db.session.get(ProductionOrder, o.id).stages[idx]
            c.post(f"/routing/start/{stage.id}", data={"operator": ("Amit Desai", "Ravi Patel", "Meena Shah")[idx % 3], "started_at": t.strftime("%Y-%m-%dT%H:%M")})
            t += timedelta(hours=1, minutes=30)
            left = round(left - 0.8, 2)
            types = ScrapType.query.order_by(ScrapType.id).all()
            f = MultiDict([("completed_at", t.strftime("%Y-%m-%dT%H:%M")), ("qty_out", str(left)), ("scrap_qty", "0.8"), ("operator", "Meena Shah"), ("scrap_type_id", str(types[idx % len(types)].id)), ("scrap_kind", "Process loss" if idx == 3 else "Saleable")])
            f.add("machine_ids", str(stage.machines[0].machine_id))
            c.post(f"/routing/complete/{stage.id}", data=f)
            db.session.expire_all()
            t += timedelta(minutes=20)
        return db.session.get(ProductionOrder, o.id)

    h = run_to_end(120, MOCK + " - ready to record output")
    i_order = run_to_end(80, MOCK + " - output recorded")
    last = i_order.stages[-1]
    c.post("/production_output/add", data={"production_order_id": str(i_order.id), "output_date": today.isoformat(), "good_qty": str(last.qty_out),
                                           "rework_qty": "1", "scrap_qty": "6.4", "recorded_by": "Meena Shah", "remarks": MOCK})

    persist_schedule()
    db.session.commit()
    print("Mock data added. Orders:")
    for o in ProductionOrder.query.order_by(ProductionOrder.id).all():
        print(f"  {o.prod_no}  {o.status:<13} qty {o.planned_qty:>6.0f}  queue {o.queue_position}  {o.remarks}")
    print("Backup of your database: instance/erp.db.before-mock")
