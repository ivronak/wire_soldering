# Production order: product choose karo, qty do, uski recipe is document pe copy ho jati hai.
# Baad mein product recipe badlegi to purana order nahi badlega.
import os
from werkzeug.utils import secure_filename
from datetime import datetime
from flask import Blueprint, flash, redirect, render_template, request, url_for
from app.extensions import db
from app.models import (Machines, Product, ProductCategories, ProductionOrder, ProductionOrderLine, ProductionOrderStage,
                        ProductionOrderStageMachine, RawMaterial)
from app.production_orders.planning import plan_stages, windows_overlap

production_orders_bp = Blueprint("production_orders", __name__, template_folder="templates")


def _is_kg(machine):
    # Plan KG me banta hai, isliye sirf wahi machine ginti hai jiski numeric capacity KG / hr me likhi ho
    unit = machine.capacity_unit.code.upper() if machine.capacity_unit else ""
    return bool(machine.capacity_per_hour) and unit in ("KG", "KGS")


def _routing_for(product):
    # Product ke default stages (Work Stage ke order me) aur har stage ki active machines — form ke plan section ke liye
    stages = []
    for row in sorted(product.routing_stages, key=lambda x: (x.work_stage.sort_order, x.work_stage.id)):
        stage = row.work_stage
        if stage is None or stage.is_deleted or not stage.is_active:
            continue
        machines = Machines.query.filter(Machines.work_stage_id == stage.id, Machines.is_deleted == False,
                                         Machines.status == "active").order_by(Machines.code).all()
        stages.append({
            "stage_id": stage.id,
            "name": stage.name,
            "machines": [{
                "id": m.id, "name": m.name, "per_hour": m.capacity_per_hour or 0, "hours_per_day": m.hours_per_day or 8,
                "ok": _is_kg(m),
            } for m in machines],
        })
    return stages


def read_plan(product, batch_kg, order_date, routing=None):
    """Form se production plan padho: har stage ki chuni hui machines aur start date. (plan, error) wapas deta hai.
    Product ka routing na ho to (None, None): order bina plan ke ban jaata hai. Server khud hisaab lagata hai (JS ke dikhaye par bharosa nahi)."""
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
        ids = request.form.getlist(f"machines_{stage['stage_id']}", type=int)
        machines = []
        for machine_id in ids:
            machine = db.session.get(Machines, machine_id)
            if machine is None or machine.is_deleted or machine.status != "active" or machine.work_stage_id != stage["stage_id"]:
                return None, f"A chosen machine is not available for {stage['name']}."
            if not _is_kg(machine):
                return None, f"{machine.name} has no output per hour in KG. Set it in Machines first."
            if machine.id in [x["id"] for x in machines]:
                continue
            machines.append({"id": machine.id, "name": machine.name, "per_hour": machine.capacity_per_hour,
                             "hours_per_day": machine.hours_per_day or 8})
        if not machines:
            return None, f"Choose at least one machine for {stage['name']}."
        chosen.append({"stage_id": stage["stage_id"], "name": stage["name"], "machines": machines})
    return plan_stages(batch_kg, chosen, start_date), None


ACTIVE_STATUSES = ("Draft", "Released")


def _bookings(exclude_order_id=None):
    """Kaun si machine kis din busy hai: {machine_id: [{order, stage, start, end}]} — sirf Draft / Released orders (Cancelled free).
    Form ka JS isi se live warning dikhata hai, server bhi isi se save rokta hai."""
    rows = (ProductionOrderStageMachine.query.join(ProductionOrderStage, ProductionOrderStageMachine.stage_id == ProductionOrderStage.id)
            .join(ProductionOrder, ProductionOrderStage.production_order_id == ProductionOrder.id)
            .filter(ProductionOrder.is_deleted == False, ProductionOrder.status.in_(ACTIVE_STATUSES),
                    ProductionOrderStage.start_date.isnot(None)))
    if exclude_order_id:
        rows = rows.filter(ProductionOrder.id != exclude_order_id)
    booked = {}
    for row in rows.all():
        stage = row.stage
        booked.setdefault(row.machine_id, []).append({
            "order": stage.production_order.prod_no, "stage": stage.stage_name,
            "start": stage.start_date.isoformat(), "end": stage.end_date.isoformat()})
    return booked


def _clashes(plan, exclude_order_id=None):
    # Plan ki har chuni machine ko doosre active orders ki booking se milao. Message order-wise ek line me
    # ("PROD-2026-001: Flux Mixer 1, Melting Furnace 1 (19 Oct to 22 Oct)") — machine-wise 11 line ka message padhna mushkil hota hai.
    booked = _bookings(exclude_order_id)
    per_order = {}
    for stage in plan["stages"]:
        for machine in stage["machines"]:
            for other in booked.get(machine["id"], []):
                other_start = datetime.strptime(other["start"], "%Y-%m-%d").date()
                other_end = datetime.strptime(other["end"], "%Y-%m-%d").date()
                if windows_overlap(stage["start_date"], stage["end_date"], other_start, other_end):
                    entry = per_order.setdefault(other["order"], {"machines": [], "start": other_start, "end": other_end})
                    if machine["name"] not in entry["machines"]:
                        entry["machines"].append(machine["name"])
                    entry["start"] = min(entry["start"], other_start)
                    entry["end"] = max(entry["end"], other_end)
    return [f"{order_no} already uses {', '.join(info['machines'])} "
            f"({info['start'].strftime('%d %b')} to {info['end'].strftime('%d %b %Y')})."
            for order_no, info in per_order.items()]


def _save_plan(order, plan):
    # Order par plan ka snapshot likho (naya order aur reschedule dono). Purane stage rows pehle hata dete hain —
    # ye plan ki copy hai (business document nahi), asli record order hi hai.
    for old in list(order.stages):
        for machine in list(old.machines):
            db.session.delete(machine)
        db.session.delete(old)
    db.session.flush()
    order.planned_start_date = plan["start_date"]
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
            })
        planner.append({
            "id": p.id,
            "code": p.code,
            "name": p.name,
            "category_id": p.category_id,
            "unit": p.base_unit.code if p.base_unit else "KG",
            "attributes": p.attributes or {},
            "routing": _routing_for(p),
            "recipe": lines,
        })
    return products, planner


@production_orders_bp.route("/production_orders")
def production_orders_list():
    # Open = Draft + Released (kaam chalu), Cancelled = alag tab (aage Completed bhi yahin judega)
    tab = request.args.get("tab", "open")
    if tab not in ("open", "cancelled"):
        tab = "open"
    base = ProductionOrder.query.filter(ProductionOrder.is_deleted == False)
    open_count = base.filter(ProductionOrder.status.in_(ACTIVE_STATUSES)).count()
    cancelled_count = base.filter(ProductionOrder.status == "Cancelled").count()
    shown = base.filter(ProductionOrder.status == "Cancelled") if tab == "cancelled" else base.filter(ProductionOrder.status.in_(ACTIVE_STATUSES))
    orders = shown.order_by(ProductionOrder.id.desc()).all()
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
                                                 Machines.status == "active").order_by(Machines.code).all()
                routing.append({"stage_id": st.work_stage_id, "name": st.stage_name, "machines": [{
                    "id": m.id, "name": m.name, "per_hour": m.capacity_per_hour or 0, "hours_per_day": m.hours_per_day or 8,
                    "ok": _is_kg(m)} for m in machines]})
            chosen = {str(st.work_stage_id): [m.machine_id for m in st.machines] for st in o.stages}
        else:
            routing = _routing_for(o.product) if o.product else []
            chosen = {}
        resched[str(o.id)] = {"prod_no": o.prod_no, "batch_kg": o.planned_qty * o.unit_weight, "routing": routing, "chosen": chosen,
                              "start": o.planned_start_date.isoformat() if o.planned_start_date else o.order_date.isoformat()}
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
        total_count=len(orders),
        result_count=len(orders),
        bookings=_bookings(),
        resched=resched,
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
    else:
        try:
            unit_weight = float(weight_raw)
        except ValueError:
            unit_weight = 0
        if unit_weight <= 0:
            flash("Enter the weight per unit in KG.", "error")
            return redirect(url_for("production_orders.production_orders_list"))

    batch_kg = planned_qty * unit_weight
    plan, plan_error = read_plan(product, batch_kg, order_date)
    if plan_error:
        flash(plan_error, "error")
        return redirect(url_for("production_orders.production_orders_list"))
    if plan and not request.form.get("allow_clash"):
        clashes = _clashes(plan)
        if clashes:
            flash("Machine clash: " + " ".join(clashes) + " Change the machines or the start date, or tick \"Save anyway\".", "error")
            return redirect(url_for("production_orders.production_orders_list"))
    year = order_date.year
    count = ProductionOrder.query.filter(ProductionOrder.prod_no.like(f"PROD-{year}-%")).count()
    prod_no = f"PROD-{year}-{count + 1:03d}"

    order = ProductionOrder(
        prod_no=prod_no,
        product_id=product.id,
        order_date=order_date,
        planned_qty=planned_qty,
        unit_weight=unit_weight,
        status="Draft",
        remarks=remarks,
        is_deleted=False,
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
        ))

    # Packaging / extra RM recipe ka percent nahi. User jo qty type kare wahi save.
    extra_ids = request.form.getlist("extra_rm_id[]")
    extra_qtys = request.form.getlist("extra_qty[]")
    seen_extra = set()
    # Jo material recipe me pehle se hai wo extra me dobara nahi aa sakta — warna aage "total material required" me double ginega
    recipe_rm_ids = {r.raw_material_id for r in product.recipe_items}
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

    db.session.commit()
    flash(f"Production order {order.prod_no} saved.", "success")
    return redirect(url_for("production_orders.production_orders_list"))



@production_orders_bp.route("/production_orders/release/<int:order_id>", methods=["POST"])
def production_orders_release(order_id):
    # Draft order ko Released karo: ab uske liye Material issue ho sakta hai (RM store se production ko).
    order = ProductionOrder.query.filter_by(id=order_id, is_deleted=False).first_or_404()
    if order.status != "Draft":
        flash("Only a draft production order can be released.", "error")
        return redirect(url_for("production_orders.production_orders_list"))
    if not order.lines:
        flash("This production order has no materials, so it cannot be released.", "error")
        return redirect(url_for("production_orders.production_orders_list"))
    order.status = "Released"
    db.session.commit()
    flash(f"Production order {order.prod_no} released. Its material can now be issued from the Material issue page.", "success")
    return redirect(url_for("production_orders.production_orders_list"))


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
    live_issues = [i.issue_no for i in order.issues if not i.is_deleted and i.status != "Cancelled"]
    if live_issues:
        flash(f"{order.prod_no} has material issues ({', '.join(live_issues)}). Cancel those in Material issue first, then cancel the order.", "error")
        return redirect(url_for("production_orders.production_orders_list"))
    order.status = "Cancelled"
    order.cancel_reason = reason[:255]
    order.cancelled_at = datetime.utcnow()
    db.session.commit()
    flash(f"Production order {order.prod_no} cancelled. Its machine booking is free again.", "success")
    return redirect(url_for("production_orders.production_orders_list"))


@production_orders_bp.route("/production_orders/reschedule/<int:order_id>", methods=["POST"])
def production_orders_reschedule(order_id):
    # Draft / Released order ki start date aur machines badlo; plan naye sire se hisaab hota hai. Qty / recipe yahan nahi badalte.
    order = ProductionOrder.query.filter_by(id=order_id, is_deleted=False).first_or_404()
    if order.status not in ACTIVE_STATUSES:
        flash("Only a draft or released production order can be rescheduled.", "error")
        return redirect(url_for("production_orders.production_orders_list"))
    routing = ([{"stage_id": st.work_stage_id, "name": st.stage_name} for st in order.stages]
               if order.stages else _routing_for(order.product))
    if not routing:
        flash("This product has no production stages. Set them in Product Master first.", "error")
        return redirect(url_for("production_orders.production_orders_list"))
    plan, plan_error = read_plan(order.product, order.planned_qty * order.unit_weight, order.order_date, routing)
    if plan_error:
        flash(plan_error, "error")
        return redirect(url_for("production_orders.production_orders_list"))
    if not request.form.get("allow_clash"):
        clashes = _clashes(plan, exclude_order_id=order.id)
        if clashes:
            flash("Machine clash: " + " ".join(clashes) + " Change the machines or the start date, or tick \"Save anyway\".", "error")
            return redirect(url_for("production_orders.production_orders_list"))
    _save_plan(order, plan)
    db.session.commit()
    flash(f"Plan updated for {order.prod_no}: ready by {plan['end_date'].strftime('%d %b %Y')}.", "success")
    return redirect(url_for("production_orders.production_orders_list"))
