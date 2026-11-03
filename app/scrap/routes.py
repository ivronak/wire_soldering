# Scrap / waste: production me jo scrap bana uska hisaab. Scrap routing me stage-wise likha jaata hai (type + Saleable / Process loss);
# yahan sab ek jagah dikhta hai: kahan, kitna, kis kisam ka, abhi kahan hai (floor / scrap yard). Stock sirf Production output post hone par banta hai.
from datetime import date, datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import FGBatch, ProductionOrder, ProductionOrderStage, ScrapPack, ScrapPackItem, ScrapType
from app.routing.routes import side_stage_info
from app.scrap.barcode import code128_svg

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
        if side_stage_info(order, st):
            continue                      # flux stage ka waste alag unit me hai, KG register me nahi
        if st.scrap_kind == "Process loss":
            where = "Process loss"
        elif order.status == "Completed":
            where = "In scrap yard"
        else:
            where = "On the floor"
        events.append({"date": st.completed_at, "order": order, "stage": st.stage_name, "type": st.scrap_type.name if st.scrap_type else "Not set",
                       "kind": st.scrap_kind, "qty": st.scrap_qty, "operator": st.operator or "", "where": where})
    return events


def active_pack_of(batch):
    # Is scrap batch ka chalta hua (unpack nahi hua) pack; nahi hai to None
    item = (ScrapPackItem.query.join(ScrapPack, ScrapPackItem.pack_id == ScrapPack.id)
            .filter(ScrapPackItem.batch_id == batch.id, ScrapPack.is_deleted == False).first())
    return item.pack if item else None


def yard_rows():
    """Scrap yard ke saare batch (output post ho chuke): [{batch, qty, types, order, where, pack}] — naya pehle."""
    rows = []
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
        rows.append({"batch": batch, "qty": qty, "types": kinds, "order": batch.production_order,
                     "where": next((m.warehouse.name for m in batch.movements if m.warehouse is not None), ""),
                     "pack": active_pack_of(batch)})
    return rows


def source_rows(batch):
    # Batch ka "kahan se aaya": order ke har stage ka saleable scrap (stage, type, operator, kab, kitna)
    return [{"batch": batch, "order": batch.production_order, "stage": st.stage_name, "type": st.scrap_type.name if st.scrap_type else "Not set",
             "qty": st.scrap_qty, "operator": st.operator or "", "when": st.completed_at}
            for st in batch.production_order.stages if st.scrap_qty and st.scrap_kind != "Process loss"]


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

    yard = yard_rows()
    yard_qty = round(sum(r["qty"] for r in yard), 4)
    # Din-wise pack banane ke liye: jin dino ka in-stock scrap abhi kisi pack me nahi (date, kitne batch, kitna KG)
    to_pack = {}
    for r in yard:
        if r["pack"] is None and r["qty"] > 0.00005:
            day = to_pack.setdefault(r["batch"].mfg_date, {"date": r["batch"].mfg_date, "count": 0, "qty": 0.0})
            day["count"] += 1
            day["qty"] = round(day["qty"] + r["qty"], 4)
    packs = ScrapPack.query.filter_by(is_deleted=False).order_by(ScrapPack.id.desc()).all()

    by_type, by_stage = {}, {}
    for e in events:
        by_type[e["type"]] = by_type.get(e["type"], 0) + e["qty"]
        by_stage[e["stage"]] = by_stage.get(e["stage"], 0) + e["qty"]
    batch_kg = sum(o.planned_qty * o.unit_weight for o in {e["order"].id: e["order"] for e in events}.values())
    total_scrap = sum(e["qty"] for e in events)
    kpi = {"yard": yard_qty, "floor": round(sum(e["qty"] for e in events if e["where"] == "On the floor"), 2),
           "loss": round(sum(e["qty"] for e in events if e["kind"] == "Process loss"), 2),
           "rate": round(100 * total_scrap / batch_kg, 1) if batch_kg else 0}
    return render_template("scrap.html", active_nav="scrap", tab=tab, kind=kind, events=shown, all_count=len(events), yard=yard, packs=packs,
                           to_pack=sorted(to_pack.values(), key=lambda d: d["date"], reverse=True),
                           kpi=kpi, by_type=_bars(by_type), by_stage=_bars(by_stage))


# ---------------- Scrap label + barcode (client change #8) ----------------
@scrap_bp.route("/scrap/label/<int:batch_id>")
def scrap_label(batch_id):
    # Scrap batch ka label: barcode (batch no) + kis stage / type / operator se kitna aaya, taaki bori par chipka ke traceability rahe
    batch = FGBatch.query.filter_by(id=batch_id, kind="SCRAP").first_or_404()
    output = batch.output
    if output is None or output.is_deleted or output.status != "Posted":
        abort(404)
    qty, _value = batch.balance
    rows = source_rows(batch)
    return render_template("scrap_label.html", batch=batch, order=batch.production_order, qty=qty, rows=rows,
                           barcode=code128_svg(batch.batch_no, height=70, module=2), pack=active_pack_of(batch))


# ---------------- Scrap pack (kai orders ka ek din ka scrap, ek barcode) ----------------
@scrap_bp.route("/scrap/pack", methods=["POST"])
def scrap_pack_create():
    # Ek din (batch ki mfg_date) ke saare in-stock, abhi tak unpacked scrap batch ek pack me
    try:
        day = datetime.strptime((request.form.get("pack_date") or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        flash("Choose the day to pack.", "error")
        return redirect(url_for("scrap.scrap_list", tab="yard"))
    batches = [r["batch"] for r in yard_rows() if r["pack"] is None and r["qty"] > 0.00005 and r["batch"].mfg_date == day]
    if not batches:
        flash(f"There is no unpacked scrap in the yard for {day.strftime('%d %b %Y')}.", "error")
        return redirect(url_for("scrap.scrap_list", tab="yard"))
    prefix = f"SCP-{day.strftime('%Y%m%d')}-"
    pack = ScrapPack(pack_no=f"{prefix}{ScrapPack.query.filter(ScrapPack.pack_no.like(prefix + '%')).count() + 1:03d}", pack_date=day, is_deleted=False)
    db.session.add(pack)
    db.session.flush()
    for batch in batches:
        db.session.add(ScrapPackItem(pack_id=pack.id, batch_id=batch.id))
    db.session.commit()
    flash(f"Pack {pack.pack_no} made from {len(batches)} scrap batch{'' if len(batches) == 1 else 'es'} ({pack.weight:g} KG). Print its label for the bag.", "success")
    return redirect(url_for("scrap.scrap_list", tab="yard"))


@scrap_bp.route("/scrap/unpack/<int:pack_id>", methods=["POST"])
def scrap_pack_remove(pack_id):
    # Delete nahi: pack hata dete hain (is_deleted) aur uske batch wapas unpacked ho jaate hain. Stock par koi asar nahi.
    pack = ScrapPack.query.filter_by(id=pack_id, is_deleted=False).first_or_404()
    pack.is_deleted = True
    db.session.commit()
    flash(f"Pack {pack.pack_no} is opened. Its batches are free to pack again.", "success")
    return redirect(url_for("scrap.scrap_list", tab="yard"))


@scrap_bp.route("/scrap/pack/label/<int:pack_id>")
def scrap_pack_label(pack_id):
    # Pack ka label: barcode (pack no) + har batch / order / stage / type / operator ka source
    pack = ScrapPack.query.filter_by(id=pack_id, is_deleted=False).first_or_404()
    # Sirf wo batch jinme abhi scrap bacha hai (output cancel ho gaya ho to us order ki rows nahi)
    rows = [row for batch in pack.batches if batch.balance[0] > 0.00005 for row in source_rows(batch)]
    return render_template("scrap_pack_label.html", pack=pack, rows=rows, weight=pack.weight,
                           barcode=code128_svg(pack.pack_no, height=70, module=2))


@scrap_bp.route("/scrap/scan")
def scrap_scan():
    # Barcode scanner keyboard jaisa hota hai: code type karke Enter. Pack no (SCP-...) ya scrap batch no (...-S) milte hi uska label khol do.
    code = " ".join((request.args.get("code") or "").split()).upper()
    if code:
        pack = ScrapPack.query.filter(ScrapPack.pack_no == code, ScrapPack.is_deleted == False).first()
        if pack is not None:
            return redirect(url_for("scrap.scrap_pack_label", pack_id=pack.id))
        batch = FGBatch.query.filter(FGBatch.batch_no == code, FGBatch.kind == "SCRAP").first()
        if batch is not None and batch.output is not None and not batch.output.is_deleted and batch.output.status == "Posted":
            return redirect(url_for("scrap.scrap_label", batch_id=batch.id))
    flash(f"No scrap pack or batch found for \"{code}\"." if code else "Scan or type a barcode first.", "error")
    return redirect(url_for("scrap.scrap_list", tab="yard"))


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
