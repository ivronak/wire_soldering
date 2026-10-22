# Scrap / waste: production me jo scrap bana uska hisaab. Scrap routing me stage-wise likha jaata hai (type + Saleable / Process loss);
# yahan sab ek jagah dikhta hai: kahan, kitna, kis kisam ka, abhi kahan hai (floor / scrap yard). Stock sirf Production output post hone par banta hai.
from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import FGBatch, ProductionOrder, ProductionOrderStage, ScrapType

scrap_bp = Blueprint("scrap", __name__, template_folder="templates")


def scrap_events():
    """Har stage ka scrap (jo Done ho chuka): [{date, order, stage, type, kind, qty, operator, where}] — naya pehle.
    where: 'On the floor' (order abhi chal raha), 'In scrap yard' (output post ho chuka, Saleable), 'Process loss' (kabhi stock nahi banta)."""
    stages = (ProductionOrderStage.query.join(ProductionOrder, ProductionOrderStage.production_order_id == ProductionOrder.id)
              .filter(ProductionOrder.is_deleted == False, ProductionOrder.status.in_(["In production", "Completed"]),
                      ProductionOrderStage.status == "Done", ProductionOrderStage.scrap_qty > 0)
              .order_by(ProductionOrderStage.completed_at.desc()).all())
    events = []
    for st in stages:
        order = st.production_order
        if st.scrap_kind == "Process loss":
            where = "Process loss"
        elif order.status == "Completed":
            where = "In scrap yard"
        else:
            where = "On the floor"
        events.append({"date": st.completed_at, "order": order, "stage": st.stage_name, "type": st.scrap_type.name if st.scrap_type else "Not set",
                       "kind": st.scrap_kind, "qty": st.scrap_qty, "operator": st.operator or "", "where": where})
    return events


def _bars(totals, limit=6):
    top = sorted(totals.items(), key=lambda kv: -kv[1])[:limit]
    biggest = top[0][1] if top else 0
    return [{"name": k, "qty": round(v, 2), "pct": int(100 * v / biggest) if biggest else 0} for k, v in top]


@scrap_bp.route("/scrap")
def scrap_list():
    tab = request.args.get("tab", "register")
    if tab not in ("register", "yard"):
        tab = "register"
    kind = request.args.get("kind", "all")
    if kind not in ("all", "Saleable", "Process loss"):
        kind = "all"
    events = scrap_events()
    shown = [e for e in events if kind == "all" or e["kind"] == kind]

    yard = []
    for batch in FGBatch.query.filter_by(kind="SCRAP").order_by(FGBatch.id.desc()).all():
        output = batch.output
        if output is None or output.is_deleted or output.status != "Posted":
            continue
        qty, _value = batch.balance
        kinds = {}
        for st in batch.production_order.stages:
            if st.scrap_qty and st.scrap_kind != "Process loss":
                name = st.scrap_type.name if st.scrap_type else "Not set"
                kinds[name] = round(kinds.get(name, 0) + st.scrap_qty, 2)
        yard.append({"batch": batch, "qty": qty, "types": kinds, "order": batch.production_order,
                     "where": next((m.warehouse.name for m in batch.movements if m.warehouse is not None), "")})
    yard_qty = round(sum(r["qty"] for r in yard), 4)

    by_type, by_stage = {}, {}
    for e in events:
        by_type[e["type"]] = by_type.get(e["type"], 0) + e["qty"]
        by_stage[e["stage"]] = by_stage.get(e["stage"], 0) + e["qty"]
    batch_kg = sum(o.planned_qty * o.unit_weight for o in {e["order"].id: e["order"] for e in events}.values())
    total_scrap = sum(e["qty"] for e in events)
    kpi = {"yard": yard_qty, "floor": round(sum(e["qty"] for e in events if e["where"] == "On the floor"), 2),
           "loss": round(sum(e["qty"] for e in events if e["kind"] == "Process loss"), 2),
           "rate": round(100 * total_scrap / batch_kg, 1) if batch_kg else 0}
    return render_template("scrap.html", active_nav="scrap", tab=tab, kind=kind, events=shown, all_count=len(events), yard=yard,
                           kpi=kpi, by_type=_bars(by_type), by_stage=_bars(by_stage))


# ---------------- Scrap types (master) ----------------
@scrap_bp.route("/scrap/types")
def scrap_types_list():
    types = ScrapType.query.filter_by(is_deleted=False).order_by(ScrapType.name).all()
    used = {t.id: ProductionOrderStage.query.filter_by(scrap_type_id=t.id).count() for t in types}
    return render_template("scrap_types.html", active_nav="scrap", types=types, used=used)


def _clean_name():
    return " ".join((request.form.get("name") or "").split())[:60]


@scrap_bp.route("/scrap/types/add", methods=["POST"])
def scrap_types_add():
    name = _clean_name()
    if not name:
        flash("Enter the scrap type name.", "error")
        return redirect(url_for("scrap.scrap_types_list"))
    if ScrapType.query.filter(db.func.lower(ScrapType.name) == name.lower()).first():
        flash(f"\"{name}\" already exists.", "error")
        return redirect(url_for("scrap.scrap_types_list"))
    db.session.add(ScrapType(name=name, is_active=True, is_deleted=False))
    db.session.commit()
    flash(f"Scrap type \"{name}\" added.", "success")
    return redirect(url_for("scrap.scrap_types_list"))


@scrap_bp.route("/scrap/types/edit/<int:type_id>", methods=["POST"])
def scrap_types_edit(type_id):
    scrap_type = ScrapType.query.filter_by(id=type_id, is_deleted=False).first_or_404()
    name = _clean_name()
    if not name:
        flash("Enter the scrap type name.", "error")
        return redirect(url_for("scrap.scrap_types_list"))
    clash = ScrapType.query.filter(db.func.lower(ScrapType.name) == name.lower(), ScrapType.id != scrap_type.id).first()
    if clash:
        flash(f"\"{name}\" already exists.", "error")
        return redirect(url_for("scrap.scrap_types_list"))
    scrap_type.name = name
    db.session.commit()
    flash("Scrap type renamed.", "success")
    return redirect(url_for("scrap.scrap_types_list"))


@scrap_bp.route("/scrap/types/toggle/<int:type_id>", methods=["POST"])
def scrap_types_toggle(type_id):
    # Delete nahi, sirf active / inactive (purana scrap record us naam ke saath rehta hai)
    scrap_type = ScrapType.query.filter_by(id=type_id, is_deleted=False).first_or_404()
    scrap_type.is_active = not scrap_type.is_active
    db.session.commit()
    flash(f"\"{scrap_type.name}\" is now {'active' if scrap_type.is_active else 'inactive'}.", "success")
    return redirect(url_for("scrap.scrap_types_list"))
