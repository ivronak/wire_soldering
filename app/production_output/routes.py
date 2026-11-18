# Production output + Finished goods: order ke saare stages poore hone par "kitna maal bana" likhna.
#   Good / Rework / Scrap likhte hi: RM WIP se use ho jaata hai, Good maal FG stock me aata hai, Scrap Scrap warehouse me, order "Completed".
# Stock ke rules: app/production_output/posting.py. Yahan sirf form, jaanch aur pages.
from datetime import date, datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.costing.fixed import apply_fixed_cost
from app.extensions import db
from app.inventory.posting import InventoryError
from app.models import FGBatch, Product, ProductCategories, ProductionOrder, ProductionOutput, Rack
from app.production_orders.scheduler import persist_schedule, renumber_queue
from app.production_orders.yield_info import short_info
from app.production_output.posting import cancel_output, fg_warehouse_for, leftover_message, leftover_rows, material_table, packed_lines, post_output, wip_lines
from app.routing.pcs import kg_per_piece, pcs_start_stage
from app.routing.routes import order_summary, side_stage_info

production_output_bp = Blueprint("production_output", __name__, template_folder="templates")

OVER_TOLERANCE = 1.10          # ordered qty se 10% tak zyada ban sakta hai


def _list_url(tab="ready"):
    return url_for("production_output.production_output_list", tab=tab)


def fg_racks_for(order):
    # Order ke FG warehouse ke chalu racks (Good maal wahin jaata hai). FG warehouse / material na ho to khaali list —
    # rack optional hai, aur asli error post karte waqt dikhegi.
    try:
        warehouse = fg_warehouse_for(order)
    except InventoryError:
        return []
    return Rack.query.filter_by(warehouse_id=warehouse.id, is_active=True, is_deleted=False).order_by(Rack.name).all()


def output_plan(order):
    """Form (drawer) ke liye: routing se bhara hua suggest (Good / Scrap), aakhri stage ki machine / operator, material table."""
    summary = order_summary(order, date.today())
    stages = summary["stages"]
    last = stages[-1]
    weight = order.unit_weight or 1
    good = round((last.qty_out or 0) / weight, 4)
    # Scrap routing me stage-wise likhi hoti hai: Saleable -> Scrap yard, Process loss -> sirf record
    # Flux jaise side stage (alag unit) ka waste product ke KG totals me nahi judta
    metal = [s for s in stages if side_stage_info(order, s) is None]
    scrap = round(sum(s.scrap_qty or 0 for s in metal if s.scrap_kind != "Process loss") / weight, 4)
    loss = round(sum(s.scrap_qty or 0 for s in metal if s.scrap_kind == "Process loss") / weight, 4)
    # G19: scrap asli me KG me gaya hota hai (jaise 25 KG dross) — PCS wala number sirf product ki unit me conversion hai, isliye KG alag se dikhate hain
    scrap_kg = round(sum(s.scrap_qty or 0 for s in metal if s.scrap_kind != "Process loss"), 3)
    unit = order.product.base_unit.code if order.product and order.product.base_unit else ""
    packed = packed_lines(order)
    # PCS wale product me asli ginti spool ki hoti hai: Spooling stage me jo spool gine (product ki unit wali packing line), wahi Good ka suggest
    counted = next((p["qty"] for p in packed if p["unit"] == unit and unit.upper() not in ("KG", "KGS")), None)
    if counted is not None:
        good = round(counted, 4)
    # C15: Spooling par PCS tick ho to Spooling ke baad ke stages (Testing, Packing) ka scrap PCS me hai (asli KG per piece se):
    # Good = bane hue spool - baad me reject hue spool; scrap / loss me wahi PCS jodte hain (pehle ke stages KG / nominal weight se, jaise pehle).
    start = pcs_start_stage(order)
    if start is not None and counted is not None:
        wa = kg_per_piece(order, start) or weight
        before = [s for s in metal if s.sort_order <= start.sort_order]
        after = [s for s in metal if s.sort_order > start.sort_order]
        scrap = round(sum(s.scrap_qty or 0 for s in before if s.scrap_kind != "Process loss") / weight
                      + sum(s.scrap_qty or 0 for s in after if s.scrap_kind != "Process loss") / wa, 2)       # piece poore hote hain: 2 decimal tak
        loss = round(sum(s.scrap_qty or 0 for s in before if s.scrap_kind == "Process loss") / weight
                     + sum(s.scrap_qty or 0 for s in after if s.scrap_kind == "Process loss") / wa, 2)
        good = round(max(counted - sum(s.scrap_qty or 0 for s in after) / wa, 0), 2)
    return {
        "order_id": order.id, "prod_no": order.prod_no, "product": order.product.name if order.product else "",
        "unit": unit, "packed": packed, "counted_from_packing": counted is not None, "unit_weight": weight,
        "planned": order.planned_qty, "extra_percent": order.extra_percent or 0, "good": good, "scrap": scrap, "scrap_kg": scrap_kg, "loss": loss, "rework": 0,
        "operator": last.operator or "", "machines": ", ".join(m.machine_name for m in last.machines if m.used),
        "last_stage": last.stage_name, "min_date": last.completed_at.date().isoformat() if last.completed_at else "",
        "materials": material_table(order),
        "leftover_note": leftover_message(order),
        "leftover": [{"id": line.id, "name": line.raw_material.name if line.raw_material else "", "qty": qty,
                      "unit": line.raw_material.base_unit.code if line.raw_material and line.raw_material.base_unit else ""} for line, qty in leftover_rows(order)],
        "racks": [] if (order.product and order.product.output_rm_id) else [{"id": rack.id, "name": rack.name} for rack in fg_racks_for(order)],
        "goes_to_store": order.product.output_rm.name if order.product and order.product.output_rm else "",
    }


@production_output_bp.route("/production_output")
def production_output_list():
    tab = request.args.get("tab", "ready")
    if tab not in ("ready", "recorded"):
        tab = "ready"
    in_production = (ProductionOrder.query.filter(ProductionOrder.is_deleted == False, ProductionOrder.status == "In production")
                     .order_by(ProductionOrder.queue_position, ProductionOrder.id).all())
    summaries = {o.id: order_summary(o, date.today()) for o in in_production}
    ready = [o for o in in_production if summaries[o.id]["all_done"]]
    waiting = [o for o in in_production if not summaries[o.id]["all_done"]]
    outputs = ProductionOutput.query.filter_by(is_deleted=False).order_by(ProductionOutput.id.desc()).all()
    plans = {o.id: output_plan(o) for o in ready}
    kpi = {"ready": len(ready), "waiting": len(waiting), "recorded": len([x for x in outputs if x.status == "Posted"]),
           "value": round(sum(x.total_value for x in outputs if x.status == "Posted"), 2)}
    return render_template("production_output.html", active_nav="production_output", tab=tab, ready=ready, waiting=waiting, summaries=summaries,
                           outputs=outputs, plans=plans, kpi=kpi, today=date.today().isoformat())


def _read_form():
    # (data, None) ya (None, "error"). Jab tak (data, None) na mile database me kuch nahi likhte.
    order_id = request.form.get("production_order_id", type=int)
    order = db.session.get(ProductionOrder, order_id) if order_id else None
    if order is None or order.is_deleted:
        return None, "Production order not found."
    if order.status != "In production":
        return None, f"{order.prod_no} is not in production, so its output cannot be recorded."
    summary = order_summary(order, date.today())
    if not summary["all_done"]:
        return None, f"All stages of {order.prod_no} must be finished first (Routing / stages)."
    if any(o.status == "Posted" and not o.is_deleted for o in order.outputs):
        return None, f"The output of {order.prod_no} is already recorded."
    try:
        output_date = datetime.strptime((request.form.get("output_date") or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        return None, "Enter a valid output date."
    if output_date > date.today():
        return None, "The output date cannot be in the future."
    last = summary["stages"][-1]
    if last.completed_at and output_date < last.completed_at.date():
        return None, f"The output date cannot be before the last stage finished ({last.completed_at.strftime('%d %b %Y')})."
    good = request.form.get("good_qty", type=float)
    rework = request.form.get("rework_qty", type=float) or 0.0
    scrap = request.form.get("scrap_qty", type=float) or 0.0
    loss = request.form.get("loss_qty", type=float) or 0.0
    if good is None or good <= 0:
        return None, "Enter the good quantity (it must be more than zero)."
    if rework < 0 or scrap < 0 or loss < 0:
        return None, "Rework, scrap and process loss cannot be negative."
    # C18: "Make extra for scrap" wale order me material (aur isliye total output) ordered se extra % zyada ho sakta hai; us par 10% ki chhoot
    allowed = order.planned_qty * (1 + (order.extra_percent or 0) / 100) * OVER_TOLERANCE
    if good + rework + scrap + loss > allowed + 0.00005:
        return None, f"Good + rework + scrap + loss ({good + rework + scrap + loss:g}) is more than 10% above the quantity planned ({allowed / OVER_TOLERANCE:g}). Check the numbers."
    if not wip_lines(order):
        return None, "No material is in production for this order. Issue material first."
    blocked = leftover_message(order)
    if blocked:
        return None, blocked
    # Rack optional; chuna ho to order ke FG warehouse ka chalu rack hona chahiye (backend pe bhi jaanch, sirf dropdown pe bharosa nahi)
    rack_raw = (request.form.get("rack_id") or "").strip()
    rack_id = int(rack_raw) if rack_raw.isdigit() else None
    if order.product and order.product.output_rm_id:
        rack_id = None                    # in-house maal RM store me jaata hai, rack nahi
    elif rack_raw and (rack_id is None or rack_id not in {rack.id for rack in fg_racks_for(order)}):
        return None, "Choose a rack that belongs to the finished goods warehouse of this order."
    return {"order": order, "output_date": output_date, "rack_id": rack_id, "good": round(good, 4), "rework": round(rework, 4), "scrap": round(scrap, 4), "loss": round(loss, 4),
            "recorded_by": (request.form.get("recorded_by") or "").strip()[:60], "remarks": (request.form.get("remarks") or "").strip()[:255]}, None


def _short_note(order):
    # C18: kam bana ho to flash me bata do ki agla kaam kahan hai (Production orders -> Completed tab)
    info = short_info(order)
    if info and info["short"]:
        return f" Ordered {info['ordered']:g} but made {info['good']:g}: short by {info['short']:g} {info['unit']}. Decide what to do on the Completed tab of Production orders."
    return ""


@production_output_bp.route("/production_output/add", methods=["POST"])
def production_output_add():
    data, error = _read_form()
    if error:
        flash(error, "error")
        return redirect(_list_url("ready"))
    order = data["order"]
    year = data["output_date"].year
    count = ProductionOutput.query.filter(ProductionOutput.output_no.like(f"OUT-{year}-%")).count()
    prefix = f"BATCH-WS-{data['output_date'].strftime('%Y%m%d')}-"
    batches = ProductionOutput.query.filter(ProductionOutput.batch_no.like(prefix + "%")).count()
    output = ProductionOutput(output_no=f"OUT-{year}-{count + 1:03d}", batch_no=f"{prefix}{batches + 1:03d}", production_order=order,
                              output_date=data["output_date"], good_qty=data["good"], rework_qty=data["rework"], scrap_qty=data["scrap"], loss_qty=data["loss"],
                              recorded_by=data["recorded_by"], remarks=data["remarks"], status="Posted", is_deleted=False)
    db.session.add(output)
    try:
        post_output(output, order, rack_id=data["rack_id"])
    except InventoryError as stock_error:
        db.session.rollback()
        flash(str(stock_error), "error")
        return redirect(_list_url("ready"))
    apply_fixed_cost(output)          # mahine ka fixed cost per KG is batch par freeze (client meeting 2, #1)
    order.status = "Completed"
    order.queue_position = None
    renumber_queue()
    persist_schedule()
    db.session.commit()
    if order.product and order.product.output_rm:
        flash(f"Output {output.output_no} recorded. {output.good_qty:g} {order.product.output_rm.name} went into raw material stock (store) and can now be issued to orders; {order.prod_no} is completed.", "success")
    else:
        flash(f"Output {output.output_no} recorded. {output.good_qty:g} good went into finished goods as batch {output.batch_no}; {order.prod_no} is completed.{_short_note(order)}", "success")
    return redirect(_list_url("recorded"))


@production_output_bp.route("/production_output/cancel/<int:output_id>", methods=["POST"])
def production_output_cancel(output_id):
    output = ProductionOutput.query.filter_by(id=output_id, is_deleted=False).first_or_404()
    if output.status != "Posted":
        flash("This output is already cancelled.", "error")
        return redirect(_list_url("recorded"))
    try:
        cancel_output(output)
    except InventoryError as stock_error:
        db.session.rollback()
        flash(str(stock_error), "error")
        return redirect(_list_url("recorded"))
    output.status = "Cancelled"
    order = output.production_order
    order.status = "In production"
    order.queue_position = None
    order.short_action = order.short_note = order.short_resolved_at = None      # C18: output hi cancel, to kami ka faisla bhi dobara hoga
    renumber_queue()
    persist_schedule()
    db.session.commit()
    flash(f"Output {output.output_no} cancelled. The material is back in production and {order.prod_no} is open again.", "success")
    return redirect(_list_url("recorded"))


@production_output_bp.route("/production_output/print/<int:output_id>")
def production_output_print(output_id):
    output = ProductionOutput.query.filter_by(id=output_id, is_deleted=False).first_or_404()
    if output.status != "Posted":
        abort(404)
    consumed = []
    from app.models import StockMovement
    for move in StockMovement.query.filter_by(ref_type="OUTPUT", ref_id=output.id, movement_type="CONSUME").filter(StockMovement.reverses_movement_id.is_(None)).all():
        consumed.append({"material": move.raw_material, "lot": move.lot, "qty": -move.qty, "value": -move.value})
    return render_template("production_output_print.html", output=output, order=output.production_order, consumed=consumed)


def _batch_party(batch):
    # Batch kis party / quotation ke order ka hai (Finalize se bana order). Koi quotation nahi = Own stock (free surplus)
    from app.models import Quotation, QuotationLine
    line = (QuotationLine.query.join(Quotation, Quotation.id == QuotationLine.quotation_id)
            .filter(QuotationLine.production_order_id == batch.production_order_id, Quotation.is_deleted == False).first())
    if line is None:
        return "Own stock"
    return f"{line.quotation.customer.name} · {line.quotation.quote_no}"


@production_output_bp.route("/finished_goods")
def finished_goods_list():
    # FG aur Scrap ka stock: batch-wise (kitna abhi maujood hai, kis cost par)
    tab = request.args.get("tab", "fg")
    if tab not in ("fg", "scrap"):
        tab = "fg"
    kind = "FG" if tab == "fg" else "SCRAP"
    batches = FGBatch.query.filter_by(kind=kind).order_by(FGBatch.id.desc()).all()
    rows = []
    for batch in batches:
        output = batch.output
        if output is None or output.is_deleted or output.status != "Posted":
            continue
        qty, value = batch.balance
        first_wh = next((m.warehouse for m in batch.movements if m.warehouse is not None), None)
        where = first_wh.name if first_wh else ""
        order = batch.production_order
        # PCS wale product: batch kitne KG ke barabar hai, aur kitne spool / box me bana (production me gine hue)
        count_unit = batch.unit_code.upper() not in ("KG", "KGS", "")
        rows.append({"batch": batch, "qty": qty, "value": value, "made": sum(m.qty for m in batch.movements if m.movement_type == "OUTPUT_IN" and m.reverses_movement_id is None),
                     "where": where, "where_type": first_wh.warehouse_type if first_wh else "", "order": order,
                     "rack": batch.rack.name if batch.rack else "",
                     "party": _batch_party(batch) if kind == "FG" else None,
                     "kg": round(qty * (order.unit_weight or 1), 2) if count_unit and kind == "FG" else None,
                     "packs": [p for p in packed_lines(order) if p["unit"] != batch.unit_code] if kind == "FG" else []})
    fg_in_stock = [r for r in rows if r["qty"] > 0.00005] if tab == "fg" else []
    kpi = {"batches": len([r for r in rows if r["qty"] > 0.00005]), "qty": round(sum(r["qty"] for r in rows), 4), "value": round(sum(r["value"] for r in rows), 2)}
    groups = fg_groups(rows) if tab == "fg" else []
    categories = fg_categories(groups) if tab == "fg" else []
    return render_template("finished_goods.html", active_nav="finished_goods", tab=tab, rows=rows, kpi=kpi, fg_in_stock=fg_in_stock, groups=groups, categories=categories)


def fg_categories(groups):
    """Client meeting 2 (#3): pehle category block (Solder Wire, Solder Stick ...), uspe click karne par products, product par click karne par batches.
    Har group ko ek 'key' milti hai (template ke batch rows ke liye). Block par qty unit ke hisaab se alag (KG + PCS ko jodte nahi)."""
    by_category = {}
    for key, group in enumerate(groups, start=1):
        group["key"] = key
        category = group["product"].category if group["product"] else None
        cat_id = category.id if category else 0
        entry = by_category.setdefault(cat_id, {"id": cat_id, "name": category.name if category else "No category", "icon": category.icon if category else None, "groups": []})
        entry["groups"].append(group)
    # Jis category ke product hain par abhi koi FG nahi, uska bhi block dikhao (0 stock) taaki saari categories ek nazar me dikhein
    for category in ProductCategories.query.filter_by(is_deleted=False, is_active=True).all():
        if category.id not in by_category and Product.query.filter_by(category_id=category.id, is_deleted=False).first():
            by_category[category.id] = {"id": category.id, "name": category.name, "icon": category.icon, "groups": []}
    result = []
    for entry in by_category.values():
        per_unit = {}
        for group in entry["groups"]:
            per_unit[group["unit"]] = per_unit.get(group["unit"], 0) + group["qty"]
        entry.update(
            qty_text=" + ".join(f"{qty:g} {unit}" for unit, qty in per_unit.items() if qty > 0.00005) or "No stock",
            value=round(sum(g["value"] for g in entry["groups"]), 2),
            products=len(entry["groups"]),
            batches=sum(g["in_stock"] for g in entry["groups"]),
            alerts=len([g for g in entry["groups"] if g["alert"]]),
            worst="bad" if any(g["alert"] and g["alert"][1] == "bad" for g in entry["groups"]) else ("warn" if any(g["alert"] for g in entry["groups"]) else ""),
        )
        result.append(entry)
    result.sort(key=lambda e: e["name"].lower())
    return result


def fg_groups(rows):
    """Tally jaisa view (client change #10): product-wise ek line (total qty); kholne par batch-wise detail.
    Alert: Out of stock (0). Below minimum / Overstock tab lagenge jab Product par min / max stock aayega (abhi sirf Raw Material par hai)."""
    by_product = {}
    for r in rows:
        product = r["batch"].product
        key = product.id if product else 0
        group = by_product.setdefault(key, {"product": product, "qty": 0.0, "value": 0.0, "batches": []})
        group["qty"] += r["qty"]
        group["value"] += r["value"]
        if r.get("kg") is not None:
            group["kg"] = group.get("kg", 0.0) + r["kg"]
        group["batches"].append(r)
    groups = []
    for group in by_product.values():
        product = group["product"]
        qty = round(group["qty"], 4)
        alert = None
        if qty <= 0.00005:
            alert = ("Out of stock", "bad")
        else:
            low, high = getattr(product, "min_stock", None), getattr(product, "max_stock", None)
            if low and qty < low:
                alert = ("Below minimum", "warn")
            elif high and qty > high:
                alert = ("Overstock", "warn")
        # Pehle jinme maal bacha hai (naya upar), used-up batch neeche
        group["batches"].sort(key=lambda r: (r["qty"] <= 0.00005, -r["batch"].id))
        category = product.category if product else None
        group.update(icon=category.icon if category else None, category=category.name if category else "",
                     low=getattr(product, "min_stock", None), high=getattr(product, "max_stock", None))
        group.update(kg=round(group["kg"], 2) if "kg" in group else None)
        group.update(qty=qty, value=round(group["value"], 2), alert=alert, in_stock=len([r for r in group["batches"] if r["qty"] > 0.00005]),
                     unit=group["batches"][0]["batch"].unit_code)
        groups.append(group)
    groups.sort(key=lambda g: (g["product"].name if g["product"] else ""))
    return groups
