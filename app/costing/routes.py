# Costing page (client meeting 2, #1): fixed cost settings, mahine ka final, aur batch-wise Product cost (material + fixed).
# Hisaab app/costing/fixed.py me; yahan sirf pages aur form ki jaanch. Abhi login / roles nahi hain, isliye page sabko dikhta hai
# (jab roles aayenge tab cost hide karna hai — client ne kaha tha accounts wale ko costing nahi dikhani).
from datetime import date, datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.costing.fixed import costed_kg, finalize_month, month_start, next_month, output_kg, period_for, posted_outputs, product_cost_per_unit
from app.extensions import db
from app.models import FixedCostMonth, FixedCostPeriod, ProductionOutput

costing_bp = Blueprint("costing", __name__, template_folder="templates")


def _url(tab, **extra):
    return url_for("costing.costing_page", tab=tab, **extra)


def _month_key(day):
    return day.strftime("%Y-%m")


def _parse_month(text):
    try:
        return datetime.strptime(text, "%Y-%m").date().replace(day=1)
    except (TypeError, ValueError):
        return None


@costing_bp.route("/costing")
def costing_page():
    tab = request.args.get("tab", "batches")
    if tab not in ("batches", "fixed", "months"):
        tab = "batches"
    today = date.today()
    all_outputs = (ProductionOutput.query.filter_by(is_deleted=False, status="Posted")
                   .order_by(ProductionOutput.output_date.desc(), ProductionOutput.id.desc()).all())
    finals = {m.month_start: m for m in FixedCostMonth.query.all()}
    month_keys = sorted({month_start(o.output_date) for o in all_outputs} | set(finals) | {month_start(today)}, reverse=True)

    # ---- Batch cost tab: FG batch (in-house RM wala maal nahi) + mahine ka filter
    picked = _parse_month(request.args.get("m", "")) or month_start(today)
    if picked not in month_keys:
        picked = month_keys[0]
    batch_rows = []
    for o in all_outputs:
        if month_start(o.output_date) != picked:
            continue
        order = o.production_order
        if order and order.product and order.product.output_rm_id:
            continue
        unit = order.product.base_unit.code if order and order.product and order.product.base_unit else ""
        per_unit = product_cost_per_unit(o)
        material_unit = (o.total_value / o.good_qty) if o.good_qty else 0
        batch_rows.append({"o": o, "product": order.product.name if order and order.product else "—", "order_no": order.prod_no if order else "",
                           "unit": unit, "kg": output_kg(o), "material_unit": material_unit, "fixed_unit": per_unit - material_unit, "cost_unit": per_unit,
                           "basis": o.fixed_cost_basis or "Material only"})
    kpi = {"batches": len(batch_rows), "material": sum(r["o"].total_value or 0 for r in batch_rows), "fixed": sum(r["o"].fixed_cost_total or 0 for r in batch_rows)}
    kpi["total"] = kpi["material"] + kpi["fixed"]
    kpi["kg"] = sum(r["kg"] for r in batch_rows)
    kpi["per_kg"] = kpi["total"] / kpi["kg"] if kpi["kg"] else 0
    any_approx = any(r["basis"] == "Approx" for r in batch_rows)

    # ---- Fixed cost tab
    periods = FixedCostPeriod.query.order_by(FixedCostPeriod.effective_from.desc(), FixedCostPeriod.id.desc()).all()
    current = period_for(today)
    first_output = min((o.output_date for o in all_outputs), default=None)

    # ---- Months tab
    months = []
    for start in month_keys:
        outs = [o for o in all_outputs if month_start(o.output_date) == start]
        final = finals.get(start)
        last_day = min(today, date.fromordinal(next_month(start).toordinal() - 1))
        period = period_for(last_day)
        months.append({"start": start, "key": _month_key(start), "kg": sum(costed_kg(o) for o in outs), "absorbed": sum(o.fixed_cost_total or 0 for o in outs),
                       "outputs": len(outs), "final": final, "estimate": period.monthly_amount if period else None,
                       "can_finalize": final is None and start <= month_start(today) and bool(outs)})
    return render_template("costing.html", active_nav="costing", tab=tab, today=today, batch_rows=batch_rows, kpi=kpi, any_approx=any_approx,
                           picked=picked, month_keys=month_keys, month_key=_month_key, periods=periods, current=current, first_output=first_output, months=months)


@costing_bp.route("/costing/period/add", methods=["POST"])
def costing_period_add():
    try:
        effective = datetime.strptime((request.form.get("effective_from") or "").strip(), "%Y-%m-%d").date()
        amount = float(request.form.get("monthly_amount") or 0)
        days = int(request.form.get("working_days") or 0)
    except ValueError:
        flash("Date, amount and working days must be valid.", "error")
        return redirect(_url("fixed"))
    note = (request.form.get("note") or "").strip()[:255]
    if amount <= 0:
        flash("Monthly fixed cost must be greater than zero.", "error")
    elif not 1 <= days <= 31:
        flash("Working days must be between 1 and 31.", "error")
    elif effective < month_start(date.today()):
        flash("The new cost can start from the first day of this month or later. Batches already recorded keep the cost they had.", "error")
    elif FixedCostMonth.query.filter_by(month_start=month_start(effective)).first():
        flash("That month is already finalised, so a new estimate cannot start in it.", "error")
    else:
        db.session.add(FixedCostPeriod(effective_from=effective, monthly_amount=round(amount, 2), working_days=days, note=note))
        db.session.commit()
        flash(f"Fixed cost of ₹{amount:,.0f} a month ({days} working days) will apply from {effective.strftime('%d %b %Y')}. Batches already recorded are not changed.", "success")
    return redirect(_url("fixed"))


@costing_bp.route("/costing/period/<int:period_id>/delete", methods=["POST"])
def costing_period_delete(period_id):
    # Sirf wahi entry hat sakti hai jisse abhi tak koi batch cost hua hi nahi (galti se daali hui future entry)
    row = db.session.get(FixedCostPeriod, period_id)
    if row is None:
        flash("That fixed cost entry does not exist.", "error")
        return redirect(_url("fixed"))
    used = ProductionOutput.query.filter(ProductionOutput.fixed_cost_basis.isnot(None), ProductionOutput.output_date >= row.effective_from).first()
    if used or row.effective_from <= date.today():
        flash("This entry is already in use (or its date has started), so it cannot be removed. Add a new entry with a later start date instead.", "error")
    else:
        db.session.delete(row)
        db.session.commit()
        flash("Fixed cost entry removed.", "success")
    return redirect(_url("fixed"))


@costing_bp.route("/costing/month/finalize", methods=["POST"])
def costing_month_finalize():
    start = _parse_month(request.form.get("month", ""))
    try:
        amount = float(request.form.get("final_amount") or 0)
    except ValueError:
        amount = 0
    if start is None:
        flash("Choose a valid month.", "error")
        return redirect(_url("months"))
    ok, result = finalize_month(start, amount)
    if not ok:
        flash(result, "error")
    else:
        db.session.commit()
        flash(f"{start.strftime('%B %Y')} finalised: ₹{result.final_amount:,.0f} over {result.total_kg:,.0f} KG = ₹{result.final_per_kg:,.2f} per KG. Batches of this month now show the final cost.", "success")
    return redirect(_url("months"))
