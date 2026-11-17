import math
# Production order: product choose karo, qty do, uski recipe is document pe copy ho jati hai.
# Baad mein product recipe badlegi to purana order nahi badlega.
import os
from werkzeug.utils import secure_filename
from datetime import datetime
from flask import abort, Blueprint, flash, jsonify, redirect, render_template, request, url_for
from app.extensions import db
from app.models import (Machines, Product, ProductCategories, ProductionLine, ProductionOrder, ProductionOrderLine, ProductionOrderStage,
                        ProductionOrderStageMachine, RawMaterial)
from app.production_orders.planning import plan_stages
from app.production_lines.status import line_board
from app.inventory.alerts import store_stock_by_material
from app.production_orders.timeline import build_timeline
from app.production_orders.scheduler import OPEN_STATUSES, live_schedule, persist_schedule, queue_orders, renumber_queue, today_ist

production_orders_bp = Blueprint("production_orders", __name__, template_folder="templates")


# Planner me kaun si machines dikhti hain: Active + temporary band (maintenance / breakdown). Retired (hamesha ke liye band) nahi dikhti.
PLANNER_MACHINE_STATUSES = ("active", "maintenance", "breakdown")


def _is_kg(machine):
    # Plan KG me banta hai, isliye sirf wahi machine ginti hai jiski numeric capacity KG / hr me likhi ho
    unit = machine.capacity_unit.code.upper() if machine.capacity_unit else ""
    return bool(machine.capacity_per_hour) and unit in ("KG", "KGS")


def _machine_row(m):
    # Planner ke liye machine ka data. line_id / line: machine kis Production Line ki hai (form me us line ki machines hi tick hoti hain)
    # G27: Breakdown / Maintenance machine bhi picker me dikhti hai (grey + label), par chun nahi sakte — isliye ok sirf Active machine ke liye True
    return {"id": m.id, "name": m.name, "per_hour": m.capacity_per_hour or 0, "hours_per_day": m.hours_per_day or 8,
            "ok": _is_kg(m) and m.status == "active", "status": m.status, "line_id": m.line_id, "line": m.line.name if m.line else ""}


def _read_line():
    # Order form ki Production Line (optional). (line, None) ya (None, "error"); khaali ho to (None, None)
    line_id = request.form.get("line_id", type=int)
    if not line_id:
        return None, None
    line = db.session.get(ProductionLine, line_id)
    if line is None or line.is_deleted or not line.is_active:
        return None, "Choose an active production line."
    return line, None


def _routing_for(product):
    # Product ke default stages (Work Stage ke order me) aur har stage ki active machines — form ke plan section ke liye
    stages = []
    for row in sorted(product.routing_stages, key=lambda x: (x.work_stage.sort_order, x.work_stage.id)):
        stage = row.work_stage
        if stage is None or stage.is_deleted or not stage.is_active:
            continue
        machines = Machines.query.filter(Machines.work_stage_id == stage.id, Machines.is_deleted == False,
                                         Machines.status.in_(PLANNER_MACHINE_STATUSES)).order_by(Machines.code).all()
        stages.append({
            "stage_id": stage.id,
            "name": stage.name,
            "machines": [_machine_row(m) for m in machines],
        })
    return stages


def read_plan(product, batch_kg, order_date, routing=None, line=None, auto=False):
    """Form se production plan padho: har stage ki chuni hui machines aur start date. (plan, error) wapas deta hai.
    Product ka routing na ho to (None, None): order bina plan ke ban jaata hai. Server khud hisaab lagata hai (JS ke dikhaye par bharosa nahi).
    line = order ki Production Line (ho to sirf usi line ki machines chun sakte hain).
    auto=True (client meeting 2, #6): order form me machine nahi chunte — har stage ki saari chalu KG-machines andaze ke liye maan lete hain;
    asli line + machines baad me Production planning page par chunte hain."""
    if routing is None:
        routing = _routing_for(product)
    if not routing:
        return None, None
    start_raw = (request.form.get("start_date") or "").strip()
    try:
        start_date = datetime.strptime(start_raw, "%Y-%m-%d").date() if start_raw else order_date
    except ValueError:
        return None, "Enter a valid start date."
    chosen = []
    for stage in routing:
        if auto:
            usable = [m for m in stage["machines"] if m["ok"]]
            if not usable:
                down = [m["name"] for m in stage["machines"] if m.get("status", "active") != "active"]
                if down:
                    return None, f"No machine is available for {stage['name']} right now: {', '.join(down)} not working (breakdown / maintenance)."
                return None, f"No machine with an output per hour in KG is set for {stage['name']}. Add one in Machines first."
            chosen.append({"stage_id": stage["stage_id"], "name": stage["name"],
                           "machines": [{"id": m["id"], "name": m["name"], "per_hour": m["per_hour"], "hours_per_day": m["hours_per_day"]} for m in usable]})
            continue
        ids = request.form.getlist(f"machines_{stage['stage_id']}", type=int)
        machines = []
        for machine_id in ids:
            machine = db.session.get(Machines, machine_id)
            if machine is None or machine.is_deleted or machine.status != "active" or machine.work_stage_id != stage["stage_id"]:
                return None, f"A chosen machine is not available for {stage['name']}."
            if line is not None and machine.line_id != line.id:
                return None, f"{machine.name} is not on {line.name}. Choose only the machines of the production line."
            if not _is_kg(machine):
                return None, f"{machine.name} has no output per hour in KG. Set it in Machines first."
            if machine.id in [x["id"] for x in machines]:
                continue
            machines.append({"id": machine.id, "name": machine.name, "per_hour": machine.capacity_per_hour,
                             "hours_per_day": machine.hours_per_day or 8})
        if not machines:
            return None, f"Choose at least one machine for {stage['name']}."
        chosen.append({"stage_id": stage["stage_id"], "name": stage["name"], "machines": machines})
    plan = plan_stages(batch_kg, chosen, start_date)
    plan["earliest_start"] = start_date
    return plan, None


# Cancel / reschedule sirf in status par (In production order frozen hai)
ACTIVE_STATUSES = ("Draft", "Released")


def posted_issued_qty(order):
    # Production ke paas abhi kitna maal hai: Posted issues (Draft nahi) minus wapas kiya hua
    total = 0.0
    for issue in order.issues:
        if issue.is_deleted or issue.status != "Posted":
            continue
        total += sum(line.qty - line.returned_qty for line in issue.lines)
    return round(total, 4)


def _read_needed_by():
    # "Needed by" optional date. (date, None) ya (None, "error"); khaali ho to (None, None)
    raw = (request.form.get("needed_by") or "").strip()
    if not raw:
        return None, None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date(), None
    except ValueError:
        return None, "Enter a valid 'needed by' date."


def _read_allowances(product):
    # Har RM ka apna allowance %: form field allowance_rm_<rm_id> (recipe + packing materials). 0 se 100; khaali = 0.
    # ({rm_id: percent}, None) ya (None, "error")
    ids = {r.raw_material_id for r in product.recipe_items} | {k.raw_material_id for k in product.packing_items}
    # Product Master me jo Spare % set hai wahi default hai (client meeting 2, #4); form me field aaye to wahi (order ke liye badla hua)
    defaults = {r.raw_material_id: r.spare_percent or 0 for r in product.recipe_items}
    defaults.update({k.raw_material_id: k.spare_percent or 0 for k in product.packing_items})
    result = {}
    for rm_id in ids:
        if f"allowance_rm_{rm_id}" not in request.form:
            result[rm_id] = round(defaults.get(rm_id, 0), 2)
            continue
        raw = (request.form.get(f"allowance_rm_{rm_id}") or "").strip()
        if not raw:
            continue
        try:
            value = float(raw)
        except ValueError:
            return None, "Enter a valid allowance percent."
        if value < 0 or value > 100:
            return None, "The allowance must be between 0 and 100 percent."
        result[rm_id] = round(value, 2)
    return result, None


def _save_plan(order, plan):
    # Order par plan ka snapshot likho (naya order aur reschedule dono). Purane stage rows pehle hata dete hain —
    # ye plan ki copy hai (business document nahi), asli record order hi hai.
    for old in list(order.stages):
        for machine in list(old.machines):
            db.session.delete(machine)
        db.session.delete(old)
    db.session.flush()
    order.earliest_start_date = plan["earliest_start"]
    order.planned_start_date = plan["start_date"]        # ye purani / andaza dates hain; queue ke hisaab se persist_schedule() badal deta hai
    order.planned_end_date = plan["end_date"]
    order.planned_hours = plan["total_hours"]
    order.planned_days = plan["working_days"]
    order.daily_capacity = plan["daily_capacity"]
    order.bottleneck_stage = plan["bottleneck"]
    for index, row in enumerate(plan["stages"]):
        stage_row = ProductionOrderStage(
            production_order_id=order.id, work_stage_id=row["stage_id"], stage_name=row["name"], sort_order=(index + 1) * 10,
            capacity_per_hour=row["per_hour"], daily_capacity=row["per_day"], planned_hours=row["hours"], planned_days=row["days"],
            start_date=row["start_date"], end_date=row["end_date"])
        db.session.add(stage_row)
        db.session.flush()
        for machine in row["machines"]:
            db.session.add(ProductionOrderStageMachine(
                stage_id=stage_row.id, machine_id=machine["id"], machine_name=machine["name"],
                capacity_per_hour=machine["per_hour"], hours_per_day=machine["hours_per_day"]))
    db.session.flush()


def _planner_products():
    products = (
        Product.query.filter(Product.is_deleted == False, Product.is_active == True)
        .order_by(Product.code)
        .all()
    )
    planner = []
    for p in products:
        lines = []
        for r in p.recipe_items:
            rm = r.raw_material
            lines.append({
                "rm_id": r.raw_material_id,
                "code": rm.code if rm else "",
                "name": rm.name if rm else "",
                "unit": rm.base_unit.code if rm and rm.base_unit else "",
                "ratio": r.ratio_percent,
                "is_flux": bool(r.is_flux),
                "spare": r.spare_percent or 0,
            })
        packing = []
        for k in p.packing_items:
            rm = k.raw_material
            packing.append({
                "rm_id": k.raw_material_id,
                "code": rm.code if rm else "",
                "name": rm.name if rm else "",
                "unit": rm.base_unit.code if rm and rm.base_unit else "",
                "kg_per_pack": k.kg_per_pack,
                "spare": k.spare_percent or 0,
            })
        planner.append({
            "id": p.id,
            "code": p.code,
            "name": p.name,
            "category_id": p.category_id,
            "unit": p.base_unit.code if p.base_unit else "KG",
            "unit_weight": p.unit_weight,
            "attributes": p.attributes or {},
            "routing": _routing_for(p),
            "recipe": lines,
            "packing": packing,
        })
    return products, planner


def bundle_counts():
    # {bundle_no: kitne (cancel nahi hue) orders} — card par 'Bundle BND-... · 3 items' chip ke liye
    rows = (db.session.query(ProductionOrder.bundle_no, db.func.count(ProductionOrder.id))
            .filter(ProductionOrder.is_deleted == False, ProductionOrder.status != "Cancelled", ProductionOrder.bundle_no.isnot(None))
            .group_by(ProductionOrder.bundle_no).all())
    return {b: n for b, n in rows}


def _new_bundle_no(year):
    # BND-<saal>-NNN: us saal ka sabse bada number + 1 (count nahi, taaki gap hone par bhi duplicate na bane)
    prefix = f"BND-{year}-"
    biggest = 0
    for (b,) in db.session.query(ProductionOrder.bundle_no).filter(ProductionOrder.bundle_no.like(prefix + "%")).distinct().all():
        try:
            biggest = max(biggest, int(b[len(prefix):]))
        except ValueError:
            pass
    return f"{prefix}{biggest + 1:03d}"


@production_orders_bp.route("/production_orders")
def production_orders_list():
    # Open = queue me saare orders (Draft / Released / In production), Cancelled = alag tab (aage Completed bhi yahin judega)
    tab = request.args.get("tab", "open")
    if tab not in ("open", "timeline", "completed", "cancelled"):
        tab = "open"
    by = "machine" if request.args.get("by") == "machine" else "order"
    base = ProductionOrder.query.filter(ProductionOrder.is_deleted == False)
    open_count = base.filter(ProductionOrder.status.in_(OPEN_STATUSES)).count()
    cancelled_count = base.filter(ProductionOrder.status == "Cancelled").count()
    completed_count = base.filter(ProductionOrder.status == "Completed").count()
    # Queue + schedule + raw material ka live hisaab ek hi baar: list isi se dikhti hai
    queue, materials, schedule = live_schedule()
    if tab == "cancelled":
        orders = base.filter(ProductionOrder.status == "Cancelled").order_by(ProductionOrder.id.desc()).all()
    elif tab == "completed":
        orders = base.filter(ProductionOrder.status == "Completed").order_by(ProductionOrder.id.desc()).all()
    else:
        orders = queue
    # ?bundle=BND-... : sirf us bundle ke orders (card ke chip se). ?add_to=BND-... : form us bundle me agla item jodne ke liye khulta hai.
    bundles = bundle_counts()
    bundle_filter = (request.args.get("bundle") or "").strip()
    if bundle_filter:
        orders = [o for o in orders if o.bundle_no == bundle_filter]
    bundle_ctx = None
    add_to = (request.args.get("add_to") or "").strip()
    if add_to:
        first = (ProductionOrder.query.filter_by(bundle_no=add_to, is_deleted=False).order_by(ProductionOrder.id).first())
        if first:
            bundle_ctx = {"bundle_no": add_to, "next_item": bundles.get(add_to, 0) + 1,
                          "order_date": first.order_date.isoformat(),
                          "needed_by": first.needed_by_date.isoformat() if first.needed_by_date else "",
                          "remarks": first.remarks or ""}
    today = today_ist()
    # Upar ke chhote cards (KPI): kitne chal rahe, kitno ko material chahiye, kitne der se
    kpi = {"running": len([o for o in queue if o.status == "In production"]),
           "material": len([o for o in queue if materials.get(o.id, {}).get("status") in ("coming", "buy")]),
           "buy": len([o for o in queue if materials.get(o.id, {}).get("status") == "buy"]),
           "late": len([o for o in queue if o.needed_by_date and schedule.get(o.id) and schedule[o.id]["end"] > o.needed_by_date])}
    # "In production" order ka progress % (aaj kitna din beet chuka us ke start se end tak)
    progress = {}
    for o in queue:
        info = schedule.get(o.id)
        if o.status == "In production" and info:
            total = max((info["end"] - info["start"]).days + 1, 1)
            progress[o.id] = int(min(max((today - info["start"]).days + 1, 0) / total, 1) * 100)
    # Routing tracker ka haal (kitne stage ho chuke, abhi kaun sa) — progress bar ab asli stages se, jab kaam shuru ho chuka ho
    stage_now = {}
    for o in queue:
        if o.status == "In production" and o.stages:
            done = len([st for st in o.stages if st.status == "Done"])
            current = next((st for st in o.stages if st.status != "Done"), None)
            stage_now[o.id] = {"done": done, "total": len(o.stages), "name": current.stage_name if current else None, "state": current.status if current else "Done"}
            if any(st.status != "Pending" for st in o.stages):
                progress[o.id] = int(100 * done / len(o.stages))
    timeline = build_timeline(queue, schedule, today, by) if tab == "timeline" else None
    products, planner = _planner_products()
    # Reschedule ke liye har open order ka data: kaun se stages, kaun si machines chuni hain, batch KG
    resched = {}
    for o in orders:
        if o.status not in ACTIVE_STATUSES:
            continue
        if o.stages:
            routing = []
            for st in o.stages:
                machines = Machines.query.filter(Machines.work_stage_id == st.work_stage_id, Machines.is_deleted == False,
                                                 Machines.status.in_(PLANNER_MACHINE_STATUSES)).order_by(Machines.code).all()
                routing.append({"stage_id": st.work_stage_id, "name": st.stage_name, "machines": [_machine_row(m) for m in machines]})
            chosen = {str(st.work_stage_id): [m.machine_id for m in st.machines] for st in o.stages}
        else:
            routing = _routing_for(o.product) if o.product else []
            chosen = {}
        earliest = o.earliest_start_date or o.planned_start_date or o.order_date
        resched[str(o.id)] = {"prod_no": o.prod_no, "batch_kg": o.planned_qty * o.unit_weight, "routing": routing, "chosen": chosen,
                              "line_id": o.line_id, "line": o.line.name if o.line else "",
                              "start": earliest.isoformat(), "needed_by": o.needed_by_date.isoformat() if o.needed_by_date else ""}
    categories = (
        ProductCategories.query.filter(
            ProductCategories.is_deleted == False,
            ProductCategories.is_active == True,
        )
        .order_by(ProductCategories.name)
        .all()
    )
    raw_materials = (
        RawMaterial.query.filter(RawMaterial.is_deleted == False, RawMaterial.is_active == True)
        .order_by(RawMaterial.code)
        .all()
    )
    material_options = [{
        "id": rm.id,
        "code": rm.code,
        "name": rm.name,
        "unit": rm.base_unit.code if rm.base_unit else "",
    } for rm in raw_materials]
    return render_template(
        "production_orders.html",
        active_nav="production_orders",
        orders=orders,
        tab=tab,
        open_count=open_count,
        cancelled_count=cancelled_count,
        completed_count=completed_count,
        total_count=len(orders),
        result_count=len(orders),
        schedule=schedule,
        materials=materials,
        today=today,
        kpi=kpi,
        progress=progress,
        stage_now=stage_now,
        timeline=timeline,
        by=by,
        store_stock={str(k): v for k, v in store_stock_by_material().items()},
        line_board=line_board(today),
        resched=resched,
        bundles=bundles,
        bundle_filter=bundle_filter,
        bundle_ctx=bundle_ctx,
        products=products,
        categories=categories,
        planner=planner,
        # Category ke attribute fields (order me): form me ek ke baad ek dropdown isi order me aate hain
        category_fields={str(c.id): list(c.attribute_fields or []) for c in categories},
        material_options=material_options,
    )


@production_orders_bp.route("/production_orders/add", methods=["POST"])
def production_orders_add():
    product_id = int(request.form.get("product_id")) if (request.form.get("product_id") or "").strip() else None
    date_raw = (request.form.get("order_date") or "").strip()
    qty_raw = (request.form.get("planned_qty") or "").strip()
    weight_raw = (request.form.get("unit_weight") or "").strip()
    remarks = (request.form.get("remarks") or "").strip()

    product = Product.query.get(product_id) if product_id else None
    if not product or product.is_deleted or not product.is_active:
        flash("Choose an active product.", "error")
        return redirect(url_for("production_orders.production_orders_list"))
    if not date_raw or not qty_raw:
        flash("Date and quantity are required.", "error")
        return redirect(url_for("production_orders.production_orders_list"))
    if not product.recipe_items:
        flash("This product has no recipe, so a production order cannot be created.", "error")
        return redirect(url_for("production_orders.production_orders_list"))

    try:
        order_date = datetime.strptime(date_raw, "%Y-%m-%d").date()
        planned_qty = float(qty_raw)
    except ValueError:
        flash("Date or quantity is not valid.", "error")
        return redirect(url_for("production_orders.production_orders_list"))
    if planned_qty <= 0:
        flash("Quantity must be greater than zero.", "error")
        return redirect(url_for("production_orders.production_orders_list"))

    unit_code = (product.base_unit.code if product.base_unit else "KG").upper()
    is_kg = unit_code in ("KG", "KGS")
    if is_kg:
        unit_weight = 1.0
    elif product.unit_weight:
        # 1 piece ka weight Product Master me fix hai — order form se nahi poochte (client meeting 2, #4)
        unit_weight = product.unit_weight
    else:
        # Purana product jiska weight Product Master me nahi bhara: form ki value chalti hai (Product me bharne ko kehte hain)
        try:
            unit_weight = float(weight_raw)
        except ValueError:
            unit_weight = 0
        if unit_weight <= 0:
            flash("Enter the weight per unit in KG (or set it once in the Product master).", "error")
            return redirect(url_for("production_orders.production_orders_list"))

    batch_kg = planned_qty * unit_weight
    # Naya form (client meeting 2, #6) line / machine nahi bhejta: planning_later=1 -> andaze ka plan, asli plan Production planning page par
    planning_later = request.form.get("planning_later") == "1"
    if planning_later:
        line, line_error = None, None
    else:
        line, line_error = _read_line()
    if line_error:
        flash(line_error, "error")
        return redirect(url_for("production_orders.production_orders_list"))
    plan, plan_error = read_plan(product, batch_kg, order_date, line=line, auto=planning_later)
    if plan_error:
        flash(plan_error, "error")
        return redirect(url_for("production_orders.production_orders_list"))
    needed_by, needed_error = _read_needed_by()
    if needed_error:
        flash(needed_error, "error")
        return redirect(url_for("production_orders.production_orders_list"))
    allowances, allowance_error = _read_allowances(product)
    if allowance_error:
        flash(allowance_error, "error")
        return redirect(url_for("production_orders.production_orders_list"))
    year = order_date.year
    count = ProductionOrder.query.filter(ProductionOrder.prod_no.like(f"PROD-{year}-%")).count()
    prod_no = f"PROD-{year}-{count + 1:03d}"

    # Bundle (client meeting 2, #5): form se bundle_no aaye to us bundle me judta hai (wo pehle se hona chahiye);
    # 'Save & add another item' dabaya aur bundle nahi tha to naya BND-... banta hai. Dono nahi to single order (bundle khaali).
    add_another = request.form.get("add_another") == "1"
    bundle_no = (request.form.get("bundle_no") or "").strip() or None
    if bundle_no and not ProductionOrder.query.filter_by(bundle_no=bundle_no, is_deleted=False).first():
        flash(f"Bundle {bundle_no[:20]} does not exist.", "error")
        return redirect(url_for("production_orders.production_orders_list"))
    if add_another and not bundle_no:
        bundle_no = _new_bundle_no(year)

    order = ProductionOrder(
        prod_no=prod_no,
        product_id=product.id,
        order_date=order_date,
        planned_qty=planned_qty,
        unit_weight=unit_weight,
        status="Draft",
        remarks=remarks,
        is_deleted=False,
        line_id=line.id if line else None,        # planner me chuni line; Start par yahi line chalti hai
        needed_by_date=needed_by,
        earliest_start_date=plan["earliest_start"] if plan else order_date,
        queue_position=(db.session.query(db.func.max(ProductionOrder.queue_position)).scalar() or 0) + 1,   # queue ke aakhir me
        plan_confirmed=not (planning_later and plan),      # andaze ka plan ho to planning baaki; plan hi nahi (stages nahi) to planning ka kuch nahi
        bundle_no=bundle_no,
    )
    db.session.add(order)
    db.session.flush()

    # Plan ke stages aur machines ki copy (master badle to purana order na badle)
    if plan:
        _save_plan(order, plan)

    # Master recipe ki id save nahi karte. Ratio aur qty is order pe copy.
    for r in product.recipe_items:
        db.session.add(ProductionOrderLine(
            production_order_id=order.id,
            raw_material_id=r.raw_material_id,
            ratio_percent=r.ratio_percent,
            required_qty=batch_kg * (r.ratio_percent or 0) / 100,
            is_flux=bool(r.is_flux),
            is_extra=False,
            work_stage_id=r.work_stage_id,
            allowance_percent=allowances.get(r.raw_material_id, 0),
        ))

    # Packing Material (spool / sleeve / box): har kg_per_pack KG par 1 pack, upar round (500 KG / 20 = 25 box). Master badle to purana order na badle.
    for k in product.packing_items:
        if not k.raw_material or k.raw_material.is_deleted or not k.kg_per_pack:
            continue
        db.session.add(ProductionOrderLine(
            production_order_id=order.id,
            raw_material_id=k.raw_material_id,
            ratio_percent=0,
            required_qty=math.ceil(round(batch_kg / k.kg_per_pack, 6)),
            is_flux=False,
            is_extra=False,
            is_packing=True,
            work_stage_id=k.work_stage_id,
            kg_per_pack=k.kg_per_pack,
            allowance_percent=allowances.get(k.raw_material_id, 0),
        ))

    # Packaging / extra RM recipe ka percent nahi. User jo qty type kare wahi save.
    extra_ids = request.form.getlist("extra_rm_id[]")
    extra_qtys = request.form.getlist("extra_qty[]")
    seen_extra = set()
    # Jo material recipe me pehle se hai wo extra me dobara nahi aa sakta — warna aage "total material required" me double ginega
    recipe_rm_ids = {r.raw_material_id for r in product.recipe_items} | {k.raw_material_id for k in product.packing_items}
    for rm_raw, qty_raw in zip(extra_ids, extra_qtys):
        rm_raw = (rm_raw or "").strip()
        qty_raw = (qty_raw or "").strip()
        if not rm_raw and not qty_raw:
            continue
        if not rm_raw or not qty_raw:
            db.session.rollback()
            flash("Each added material needs a raw material and a quantity.", "error")
            return redirect(url_for("production_orders.production_orders_list"))
        try:
            rm_id = int(rm_raw)
            extra_qty = float(qty_raw)
        except ValueError:
            db.session.rollback()
            flash("An added material line is not valid.", "error")
            return redirect(url_for("production_orders.production_orders_list"))
        if extra_qty <= 0:
            db.session.rollback()
            flash("Added material quantity must be greater than zero.", "error")
            return redirect(url_for("production_orders.production_orders_list"))
        if rm_id in seen_extra:
            db.session.rollback()
            flash("The same extra material is added twice. Keep one line and change its quantity.", "error")
            return redirect(url_for("production_orders.production_orders_list"))
        rm = RawMaterial.query.get(rm_id)
        if not rm or rm.is_deleted or not rm.is_active:
            db.session.rollback()
            flash("Choose an active raw material for the added line.", "error")
            return redirect(url_for("production_orders.production_orders_list"))
        if rm_id in recipe_rm_ids:
            db.session.rollback()
            flash(f"{rm.name} is already part of this product's recipe. Its quantity is worked out from the recipe, so do not add it again as extra material.", "error")
            return redirect(url_for("production_orders.production_orders_list"))
        seen_extra.add(rm_id)
        db.session.add(ProductionOrderLine(
            production_order_id=order.id,
            raw_material_id=rm.id,
            ratio_percent=0,
            required_qty=extra_qty,
            is_flux=False,
            is_extra=True,
        ))

    persist_schedule()
    db.session.commit()
    if add_another:
        flash(f"Production order {order.prod_no} saved in bundle {bundle_no}. Add the next item for the same order below.", "success")
        return redirect(url_for("production_orders.production_orders_list", add_to=bundle_no))
    if bundle_no:
        flash(f"Production order {order.prod_no} saved and added to bundle {bundle_no} at the end of the queue.", "success")
        return redirect(url_for("production_orders.production_orders_list", bundle=bundle_no))
    flash(f"Production order {order.prod_no} saved and added to the end of the queue.", "success")
    return redirect(url_for("production_orders.production_orders_list"))



@production_orders_bp.route("/production_orders/expected", methods=["POST"])
def production_orders_expected():
    """Order form ke liye "Expected delivery date" (client meeting 2, #6): sales / accounts wale ko line-machine nahi, bas ye dikhna chahiye ki
    ye order daalne par kab tak tayyar hoga. Naya order queue ke aakhir me rakh kar (andaze ke machines se) asli scheduler chalate hain
    (queue, machines, raw material sab ginta hai) aur sab kuch wapas rollback — DB me kuch nahi bachta. JSON: {ok, start, end, text, ...}."""
    product = db.session.get(Product, request.form.get("product_id", type=int) or 0)
    qty = request.form.get("planned_qty", type=float) or 0
    if not product or product.is_deleted or not product.is_active or not product.recipe_items or qty <= 0:
        return jsonify({"ok": False, "text": "Choose a product and a quantity."})
    unit_code = (product.base_unit.code if product.base_unit else "KG").upper()
    unit_weight = 1.0 if unit_code in ("KG", "KGS") else (product.unit_weight or request.form.get("unit_weight", type=float) or 0)
    if unit_weight <= 0:
        return jsonify({"ok": False, "text": "Enter the weight per unit."})
    batch_kg = qty * unit_weight
    today = today_ist()
    plan, error = read_plan(product, batch_kg, today, auto=True)
    if error:
        return jsonify({"ok": False, "text": error})
    if not plan:
        return jsonify({"ok": False, "text": "This product has no production stages, so no date can be worked out."})
    try:
        order = ProductionOrder(prod_no="PREVIEW", product_id=product.id, order_date=today, planned_qty=qty, unit_weight=unit_weight, status="Draft", is_deleted=False,
                                earliest_start_date=plan["earliest_start"], queue_position=(db.session.query(db.func.max(ProductionOrder.queue_position)).scalar() or 0) + 1)
        db.session.add(order)
        db.session.flush()
        _save_plan(order, plan)
        for r in product.recipe_items:
            db.session.add(ProductionOrderLine(production_order_id=order.id, raw_material_id=r.raw_material_id, ratio_percent=r.ratio_percent,
                                               required_qty=batch_kg * (r.ratio_percent or 0) / 100, is_flux=bool(r.is_flux), is_extra=False, work_stage_id=r.work_stage_id))
        for k in product.packing_items:
            if k.raw_material and not k.raw_material.is_deleted and k.kg_per_pack:
                db.session.add(ProductionOrderLine(production_order_id=order.id, raw_material_id=k.raw_material_id, ratio_percent=0, is_packing=True,
                                                   required_qty=math.ceil(round(batch_kg / k.kg_per_pack, 6)), is_flux=False, is_extra=False, work_stage_id=k.work_stage_id, kg_per_pack=k.kg_per_pack))
        db.session.flush()
        db.session.expire(order, ["stages", "lines"])          # stages / lines abhi id se jude hain; collection naye sire se load ho
        _queue, materials, schedule = live_schedule(today)
        info = schedule.get(order.id)
        status = (materials.get(order.id) or {}).get("status", "ok")
        result = None
        if info:
            result = {"ok": True, "start": info["start"].isoformat(), "end": info["end"].isoformat(), "end_text": info["end"].strftime("%d %b %Y"),
                      "days": info["working_days"], "material": status,
                      "waits_for_material": info["waits_for_material"].strftime("%d %b %Y") if info["waits_for_material"] else None}
    finally:
        db.session.rollback()          # preview hai: kuch save nahi hota
    return jsonify(result or {"ok": False, "text": "A stage has no machine capacity, so no date can be worked out."})


def _back_url():
    # Production planning page se aaye hain (form me next=planning) to wahin wapas bhejo; sirf yahi ek value allowed (open redirect nahi)
    if request.form.get("next") == "planning":
        return url_for("production_planning.production_planning_page")
    return url_for("production_orders.production_orders_list")


@production_orders_bp.route("/production_orders/release/<int:order_id>", methods=["POST"])
def production_orders_release(order_id):
    # Draft order ko Released karo: ab uske liye Material issue ho sakta hai (RM store se production ko).
    order = ProductionOrder.query.filter_by(id=order_id, is_deleted=False).first_or_404()
    if order.status != "Draft":
        flash("Only a draft production order can be released.", "error")
        return redirect(_back_url())
    if not order.lines:
        flash("This production order has no materials, so it cannot be released.", "error")
        return redirect(_back_url())
    if not order.plan_confirmed:
        flash(f"Plan {order.prod_no} first: choose its production line and machines on the Production planning page, then release it.", "error")
        return redirect(_back_url())
    order.status = "Released"
    db.session.commit()
    flash(f"Production order {order.prod_no} released. Its material can now be issued from the Material issue page.", "success")
    return redirect(_back_url())


@production_orders_bp.route("/production_orders/cancel/<int:order_id>", methods=["POST"])
def production_orders_cancel(order_id):
    # Order delete nahi hota, status "Cancelled" + wajah (audit). Material issue ho chuka (ya draft issue pada) ho to cancel nahi:
    # pehle wo issues cancel karo taaki stock wapas store me aaye — warna WIP me phansa maal bhool jaayega.
    order = ProductionOrder.query.filter_by(id=order_id, is_deleted=False).first_or_404()
    if order.status not in ACTIVE_STATUSES:
        flash("Only a draft or released production order can be cancelled.", "error")
        return redirect(url_for("production_orders.production_orders_list"))
    reason = (request.form.get("reason") or "").strip()
    if not reason:
        flash("Enter the reason for cancelling.", "error")
        return redirect(url_for("production_orders.production_orders_list"))
    # Draft issue pada ho, ya production me abhi maal (issue - return) bacha ho to cancel nahi: pehle wo store me wapas karo
    drafts = [i.issue_no for i in order.issues if not i.is_deleted and i.status == "Draft"]
    in_wip = [l for l in order.lines if l.issued_qty > 0.00005]
    if drafts or in_wip:
        flash(f"{order.prod_no} still has material issued to production" + (f" ({', '.join(drafts)} draft)" if drafts else "") +
              ". Return the unused material to the store (Material issue, Return) or cancel the issues first, then cancel the order.", "error")
        return redirect(url_for("production_orders.production_orders_list"))
    order.status = "Cancelled"
    order.cancel_reason = reason[:255]
    order.cancelled_at = datetime.utcnow()
    order.queue_position = None
    renumber_queue()
    persist_schedule()
    db.session.commit()
    flash(f"Production order {order.prod_no} cancelled. Its place in the queue and its machines are free again.", "success")
    return redirect(url_for("production_orders.production_orders_list"))


@production_orders_bp.route("/production_orders/reschedule/<int:order_id>", methods=["POST"])
def production_orders_reschedule(order_id):
    # Draft / Released order ki start date aur machines badlo; plan naye sire se hisaab hota hai. Qty / recipe yahan nahi badalte.
    order = ProductionOrder.query.filter_by(id=order_id, is_deleted=False).first_or_404()
    if order.status not in ACTIVE_STATUSES:
        flash("Only a draft or released production order can be rescheduled.", "error")
        return redirect(_back_url())
    routing = ([{"stage_id": st.work_stage_id, "name": st.stage_name} for st in order.stages]
               if order.stages else _routing_for(order.product))
    if not routing:
        flash("This product has no production stages. Set them in Product Master first.", "error")
        return redirect(_back_url())
    # Line badal sakte hain (spec 28.1: dusri line me move possible). Form me line na aaye to order ki purani line; us line ki machines hi chun sakte hain.
    line, line_error = _read_line()
    if line_error:
        flash(line_error, "error")
        return redirect(_back_url())
    line = line or order.line
    plan, plan_error = read_plan(order.product, order.planned_qty * order.unit_weight, order.order_date, routing, line=line)
    if plan_error:
        flash(plan_error, "error")
        return redirect(_back_url())
    needed_by, needed_error = _read_needed_by()
    if needed_error:
        flash(needed_error, "error")
        return redirect(_back_url())
    order.needed_by_date = needed_by
    order.line_id = line.id if line else None
    order.plan_confirmed = True          # line + machines ab production manager ne chun li (Production planning)
    _save_plan(order, plan)
    persist_schedule()
    db.session.commit()
    flash(f"Plan updated for {order.prod_no}. Its start and finish dates now come from its place in the queue.", "success")
    return redirect(_back_url())


@production_orders_bp.route("/production_orders/move/<int:order_id>/<direction>", methods=["POST"])
def production_orders_move(order_id, direction):
    # Queue me order ko upar / neeche / sabse aage karo. "In production" orders frozen hain (hamesha sabse aage), unhe nahi hilate.
    order = ProductionOrder.query.filter_by(id=order_id, is_deleted=False).first_or_404()
    if order.status not in ACTIVE_STATUSES:
        flash("Only a draft or released order can be moved in the queue.", "error")
        return redirect(url_for("production_orders.production_orders_list"))
    if direction not in ("up", "down", "first"):
        abort(404)
    waiting = [o for o in queue_orders() if o.status in ACTIVE_STATUSES]
    index = waiting.index(order)
    if direction == "first":
        waiting.insert(0, waiting.pop(index))
    elif direction == "up" and index > 0:
        waiting[index - 1], waiting[index] = waiting[index], waiting[index - 1]
    elif direction == "down" and index < len(waiting) - 1:
        waiting[index + 1], waiting[index] = waiting[index], waiting[index + 1]
    frozen = [o for o in queue_orders() if o.status == "In production"]
    for position, item in enumerate(frozen + waiting, start=1):
        item.queue_position = position
    db.session.flush()
    persist_schedule()
    db.session.commit()
    flash(f"{order.prod_no} is now number {order.queue_position} in the queue.", "success")
    return redirect(url_for("production_orders.production_orders_list"))


@production_orders_bp.route("/production_orders/start/<int:order_id>", methods=["POST"])
def production_orders_start(order_id):
    # Released order ko "In production" karo. Uski dates aaj se shuru hoke us waqt freeze ho jaati hain; baaki queue un ke aas-paas chalti hai.
    order = ProductionOrder.query.filter_by(id=order_id, is_deleted=False).first_or_404()
    if order.status != "Released":
        flash("Only a released production order can be started.", "error")
        return redirect(url_for("production_orders.production_orders_list"))
    if order.issue_status == "Not issued":
        flash(f"Issue material for {order.prod_no} first (Material issue page), then start production.", "error")
        return redirect(url_for("production_orders.production_orders_list"))
    if posted_issued_qty(order) <= 0.00005:
        # Draft issue stock nahi hilata — production ke paas maal tab hi hai jab issue Post ho chuka ho
        flash(f"{order.prod_no} only has a draft material issue. Post it (Material issue page) so the material reaches production, then start.", "error")
        return redirect(url_for("production_orders.production_orders_list"))
    if not order.stages:
        flash("This order has no production plan (stages and machines). Add one with Reschedule first.", "error")
        return redirect(url_for("production_orders.production_orders_list"))
    today = today_ist()
    # Is order ko frozen waalon ke turant baad rakh ke aaj se schedule karo, uski dates save karo
    queue = queue_orders()
    frozen = [o for o in queue if o.status == "In production"]
    rest = [o for o in queue if o.status != "In production" and o.id != order.id]
    ordered, _materials, schedule = live_schedule(today, frozen + [order] + rest, {order.id: today})
    info = schedule.get(order.id)
    if not info:
        flash("This order's plan is incomplete (a stage has no machine capacity).", "error")
        return redirect(url_for("production_orders.production_orders_list"))
    for stage, (start, end) in zip(order.stages, info["windows"]):
        stage.start_date = start
        stage.end_date = end
    # Production line: lines bani hon to chunna zaroori (client change #1); koi line nahi to pehle jaisa chalta hai
    # In-house product (Flux) ka order line ki capacity / "line chuno" se bandha nahi: wo alag se store ke liye banta hai (client meeting 2, #9)
    in_house = bool(order.product and order.product.output_rm_id)
    board = [] if in_house else line_board(today)
    if board:
        # Order banate waqt line chuni thi (machines usi ki) to wahi; warna Start ke form se (purane orders)
        line_id = order.line_id or request.form.get("line_id", type=int)
        if line_id not in {row["id"] for row in board}:
            flash("The production line of this order is not active any more. Turn it on in Production Lines first." if order.line_id
                  else "Choose the production line for this order.", "error")
            return redirect(url_for("production_orders.production_orders_list"))
        order.line_id = line_id
        # Line ki daily capacity se kam kaam (is order + us line par baaki chalte orders) ho to wajah likhna zaroori
        chosen = next(row for row in board if row["id"] == line_id)
        batch_kg = (order.planned_qty or 0) * (order.unit_weight or 1)
        gap = round(chosen["capacity"] - (chosen["left_kg"] + batch_kg), 2)
        reason = (request.form.get("under_reason") or "").strip()[:255]
        if gap > 0.0001:
            if len(reason) < 3:
                flash(f"{chosen['name']} can make {chosen['capacity']:g} KG a day but only {chosen['left_kg'] + batch_kg:g} KG is planned. "
                      f"Write why {gap:g} KG of its capacity is unused (or add another order first).", "error")
                return redirect(url_for("production_orders.production_orders_list"))
            order.under_capacity_kg = gap
            order.under_capacity_reason = reason
        else:
            order.under_capacity_kg = None
            order.under_capacity_reason = None
    order.planned_start_date = info["start"]
    order.planned_end_date = info["end"]
    order.earliest_start_date = today
    order.started_date = today
    order.status = "In production"
    renumber_queue()
    persist_schedule(today)
    db.session.commit()
    line_text = f" on {order.line.name}" if order.line else ""
    flash(f"{order.prod_no} is now in production{line_text}. Planned finish: {info['end'].strftime('%d %b %Y')}.", "success")
    return redirect(url_for("production_orders.production_orders_list"))


@production_orders_bp.route("/production_orders/<int:order_id>/print")
def production_orders_print(order_id):
    # Production order ka A4 print (Nrupex letterhead). Dates queue ke live hisaab se (cancelled order ki nahi).
    order = ProductionOrder.query.filter_by(id=order_id, is_deleted=False).first_or_404()
    _queue, _materials, schedule = live_schedule()
    return render_template("production_order_print.html", order=order, sc=schedule.get(order.id) if order.status != "Cancelled" else None)
