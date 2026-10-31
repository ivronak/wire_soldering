# Production output + Finished goods: order ke saare stages poore hone par "kitna maal bana" likhna.
#   Good / Rework / Scrap likhte hi: RM WIP se use ho jaata hai, Good maal FG stock me aata hai, Scrap Scrap warehouse me, order "Completed".
# Stock ke rules: app/production_output/posting.py. Yahan sirf form, jaanch aur pages.
from datetime import date, datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.inventory.posting import InventoryError
from app.models import FGBatch, ProductionOrder, ProductionOutput, Rack
from app.production_orders.scheduler import persist_schedule, renumber_queue
from app.production_output.posting import cancel_output, fg_warehouse_for, material_table, post_output, wip_lines
from app.routing.routes import order_summary

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
    scrap = round(sum(s.scrap_qty or 0 for s in stages if s.scrap_kind != "Process loss") / weight, 4)
    loss = round(sum(s.scrap_qty or 0 for s in stages if s.scrap_kind == "Process loss") / weight, 4)
    return {
        "order_id": order.id, "prod_no": order.prod_no, "product": order.product.name if order.product else "",
        "unit": order.product.base_unit.code if order.product and order.product.base_unit else "",
        "planned": order.planned_qty, "good": good, "scrap": scrap, "loss": loss, "rework": 0,
        "operator": last.operator or "", "machines": ", ".join(m.machine_name for m in last.machines if m.used),
        "last_stage": last.stage_name, "min_date": last.completed_at.date().isoformat() if last.completed_at else "",
        "materials": material_table(order),
        "racks": [{"id": rack.id, "name": rack.name} for rack in fg_racks_for(order)],
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
    if good + rework + scrap + loss > order.planned_qty * OVER_TOLERANCE + 0.00005:
        return None, f"Good + rework + scrap + loss ({good + rework + scrap + loss:g}) is more than 10% above the ordered quantity ({order.planned_qty:g}). Check the numbers."
    if not wip_lines(order):
        return None, "No material is in production for this order. Issue material first."
    # Rack optional; chuna ho to order ke FG warehouse ka chalu rack hona chahiye (backend pe bhi jaanch, sirf dropdown pe bharosa nahi)
    rack_raw = (request.form.get("rack_id") or "").strip()
    rack_id = int(rack_raw) if rack_raw.isdigit() else None
    if rack_raw and (rack_id is None or rack_id not in {rack.id for rack in fg_racks_for(order)}):
        return None, "Choose a rack that belongs to the finished goods warehouse of this order."
    return {"order": order, "output_date": output_date, "rack_id": rack_id, "good": round(good, 4), "rework": round(rework, 4), "scrap": round(scrap, 4), "loss": round(loss, 4),
            "recorded_by": (request.form.get("recorded_by") or "").strip()[:60], "remarks": (request.form.get("remarks") or "").strip()[:255]}, None


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
    order.status = "Completed"
    order.queue_position = None
    renumber_queue()
    persist_schedule()
    db.session.commit()
    flash(f"Output {output.output_no} recorded. {output.good_qty:g} good went into finished goods as batch {output.batch_no}; {order.prod_no} is completed.", "success")
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
        where = next((m.warehouse.name for m in batch.movements if m.warehouse is not None), "")
        rows.append({"batch": batch, "qty": qty, "value": value, "made": sum(m.qty for m in batch.movements if m.movement_type == "OUTPUT_IN" and m.reverses_movement_id is None),
                     "where": where, "order": batch.production_order, "rack": batch.rack.name if batch.rack else ""})
    fg_in_stock = [r for r in rows if r["qty"] > 0.00005] if tab == "fg" else []
    kpi = {"batches": len([r for r in rows if r["qty"] > 0.00005]), "qty": round(sum(r["qty"] for r in rows), 4), "value": round(sum(r["value"] for r in rows), 2)}
    groups = fg_groups(rows) if tab == "fg" else []
    return render_template("finished_goods.html", active_nav="finished_goods", tab=tab, rows=rows, kpi=kpi, fg_in_stock=fg_in_stock, groups=groups)


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
        group.update(qty=qty, value=round(group["value"], 2), alert=alert, in_stock=len([r for r in group["batches"] if r["qty"] > 0.00005]),
                     unit=group["batches"][0]["batch"].unit_code)
        groups.append(group)
    groups.sort(key=lambda g: (g["product"].name if g["product"] else ""))
    return groups
