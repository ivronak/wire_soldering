# Consumption variance: planned (recipe) vs actual (kitna raw material asal me laga) har material ka, aur output ka yield / process loss.
# Variance = Actual - Planned: + zyada laga (cost badhi), - kam laga. Actual: output post ho chuka to CONSUME rows (WIP se use hua maal),
# warna abhi tak production ko diya gaya (issue - return) — "so far". Yahan kuch save nahi hota, sirf "Mark reviewed" ko chhodkar.
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import ProductionOrder, ProductionOutput, StockMovement
from app.production_orders.scheduler import now_ist
from app.production_output.posting import material_table, wip_lines

variance_bp = Blueprint("variance", __name__, template_folder="templates")

TOLERANCE_PCT = 2.0          # itne % tak ka farak "On plan" ginte hain


def _status(variance, planned):
    if planned <= 0:
        return "ok" if abs(variance) < 0.00005 else ("over" if variance > 0 else "under")
    pct = 100.0 * variance / planned
    if pct > TOLERANCE_PCT:
        return "over"
    if pct < -TOLERANCE_PCT:
        return "under"
    return "ok"


def order_variance(order, output=None):
    """Ek order ka variance. output diya ho (Posted) to final, warna 'so far'. Wapas dict (JSON-friendly values)."""
    final = output is not None
    actual_by_line, value_by_line, lots_by_line = {}, {}, {}
    if final:
        moves = StockMovement.query.filter_by(ref_type="OUTPUT", ref_id=output.id, movement_type="CONSUME").filter(StockMovement.reverses_movement_id.is_(None)).all()
        issue_line_to_order_line = {}
        for issue in order.issues:
            for line in issue.lines:
                issue_line_to_order_line[str(line.id)] = line.production_order_line_id
        for move in moves:
            order_line_id = issue_line_to_order_line.get(move.line_key)
            if order_line_id is None:
                continue
            actual_by_line[order_line_id] = actual_by_line.get(order_line_id, 0) + (-move.qty)
            value_by_line[order_line_id] = value_by_line.get(order_line_id, 0) + (-move.value)
            lots_by_line.setdefault(order_line_id, []).append({"lot": move.lot.lot_code if move.lot else "", "batch": move.lot.vendor_batch_no if move.lot else "",
                                                               "qty": round(-move.qty, 4), "value": round(-move.value, 2)})
    else:
        table = {t["code"]: t for t in material_table(order)}
        for order_line in order.lines:
            rm = order_line.raw_material
            row = table.get(rm.code) if rm else None
            if row:
                actual_by_line[order_line.id] = row["issued"]
                value_by_line[order_line.id] = row["value"]
        for line, net in wip_lines(order):
            lots_by_line.setdefault(line.production_order_line_id, []).append({"lot": line.lot.lot_code if line.lot else "", "batch": line.lot.vendor_batch_no if line.lot else "",
                                                                                 "qty": net, "value": None})
    lines = []
    impact_total = 0.0
    over = under = 0
    input_kg = 0.0
    for order_line in order.lines:
        rm = order_line.raw_material
        unit = rm.base_unit.code if rm and rm.base_unit else ""
        planned = round(order_line.required_qty, 4)
        actual = round(actual_by_line.get(order_line.id, 0), 4)
        variance = round(actual - planned, 4)
        value = value_by_line.get(order_line.id, 0)
        unit_cost = (value / actual) if actual else 0
        impact = round(variance * unit_cost, 2)
        status = _status(variance, planned)
        over += status == "over"
        under += status == "under"
        impact_total += impact
        if unit.upper() in ("KG", "KGS"):
            input_kg += actual
        lines.append({"name": rm.name if rm else "", "code": rm.code if rm else "", "unit": unit, "planned": planned, "actual": actual, "variance": variance,
                      "pct": round(100.0 * variance / planned, 1) if planned else 0, "impact": impact, "status": status, "unit_cost": round(unit_cost, 2),
                      "lots": lots_by_line.get(order_line.id, [])})
    result = {"final": final, "lines": lines, "over": over, "under": under, "impact": round(impact_total, 2),
              "status": "over" if over else ("under" if under else "ok")}
    insights = []
    for ln in lines:
        if ln["status"] == "over":
            insights.append(f"{ln['name']}: {abs(ln['variance']):g} {ln['unit']} more than planned (about ₹{abs(ln['impact']):,.0f} extra).")
        elif ln["status"] == "under":
            insights.append(f"{ln['name']}: {abs(ln['variance']):g} {ln['unit']} less than planned (about ₹{abs(ln['impact']):,.0f} saved).")
    if not insights:
        insights.append("Every material was used as planned (within %g%%)." % TOLERANCE_PCT)
    result["insights"] = insights
    if final:
        weight = order.unit_weight or 1
        ordered = order.planned_qty
        out_total = output.good_qty + output.rework_qty + output.scrap_qty + output.loss_qty
        output_kg = round(out_total * weight, 4)
        result["output"] = {
            "ordered": ordered, "good": output.good_qty, "rework": output.rework_qty, "scrap": output.scrap_qty, "loss": output.loss_qty,
            "unit": order.product.base_unit.code if order.product and order.product.base_unit else "",
            "yield_pct": round(100.0 * output.good_qty / ordered, 1) if ordered else 0,
            "scrap_pct": round(100.0 * (output.scrap_qty + output.loss_qty) / ordered, 1) if ordered else 0,
            "input_kg": round(input_kg, 3), "output_kg": output_kg, "unaccounted_kg": round(input_kg - output_kg, 3),
            "unit_cost": output.unit_cost, "total_value": output.total_value,
        }
    return result


@variance_bp.route("/consumption_variance")
def variance_list():
    tab = request.args.get("tab", "done")
    if tab not in ("done", "running"):
        tab = "done"
    result_filter = request.args.get("result", "all")
    if result_filter not in ("all", "over", "under", "ok"):
        result_filter = "all"

    outputs = ProductionOutput.query.filter_by(status="Posted", is_deleted=False).order_by(ProductionOutput.id.desc()).all()
    done_rows = []
    for out in outputs:
        v = order_variance(out.production_order, out)
        done_rows.append({"order": out.production_order, "output": out, "v": v})
    running = (ProductionOrder.query.filter(ProductionOrder.is_deleted == False, ProductionOrder.status == "In production")
               .order_by(ProductionOrder.queue_position, ProductionOrder.id).all())
    running_rows = [{"order": o, "output": None, "v": order_variance(o)} for o in running]

    rows = done_rows if tab == "done" else running_rows
    shown = [r for r in rows if result_filter == "all" or r["v"]["status"] == result_filter]
    kpi = {
        "checked": len(done_rows),
        "over": round(sum(max(r["v"]["impact"], 0) for r in done_rows), 2),
        "under": round(sum(min(r["v"]["impact"], 0) for r in done_rows), 2),
        "yield": round(sum(r["v"]["output"]["yield_pct"] for r in done_rows) / len(done_rows), 1) if done_rows else None,
        "review": len([r for r in done_rows if r["output"].reviewed_at is None]),
    }
    return render_template("consumption_variance.html", active_nav="variance", tab=tab, result_filter=result_filter, rows=shown, kpi=kpi,
                           done_count=len(done_rows), running_count=len(running_rows), tolerance=TOLERANCE_PCT)


@variance_bp.route("/consumption_variance/review/<int:output_id>", methods=["POST"])
def variance_review(output_id):
    output = ProductionOutput.query.filter_by(id=output_id, is_deleted=False, status="Posted").first_or_404()
    if output.reviewed_at is not None:
        flash("This variance has already been reviewed.", "error")
        return redirect(url_for("variance.variance_list"))
    by = (request.form.get("reviewed_by") or "").strip()[:60]
    if not by:
        flash("Enter your name to mark this as reviewed.", "error")
        return redirect(url_for("variance.variance_list"))
    output.reviewed_by = by
    output.review_note = (request.form.get("review_note") or "").strip()[:255] or None
    output.reviewed_at = now_ist()
    db.session.commit()
    flash(f"Variance of {output.production_order.prod_no} marked as reviewed.", "success")
    return redirect(url_for("variance.variance_list"))
