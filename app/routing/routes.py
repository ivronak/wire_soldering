# Routing / stages tracker: In production order ke har stage ka ASLI kaam — kisne, kaun si machine, kab se kab tak, kitna maal nikla — plan ke saath.
# Stage ek ke baad ek chalte hain (Pending -> In progress -> Done). Stage kabhi delete nahi hota; galti ho to sirf aakhri Done stage "Reopen" hota hai.
# Plan (stages / machines / dates) production_orders me bana hai; yahan sirf asli record aur plan se farak (late / early) dikhta hai.
import math
import os
from datetime import datetime, timedelta

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Machines, ProductionOrder, ProductionOrderStage, ProductionOrderStageMachine, ScrapType, StageLabQC
from app.production_orders.planning import next_working_day
from app.production_orders.scheduler import now_ist, today_ist

routing_bp = Blueprint("routing", __name__, template_folder="templates")

EPS = 0.0001


def _back(tab="running"):
    return redirect(url_for("routing.routing_list", tab=tab))


def order_batch_kg(order):
    return round(order.planned_qty * order.unit_weight, 4)


def side_stage_info(order, stage):
    """Flux Preparation jaisa "side" stage: iski saari material lines flux ki hon to iska maal metal chain me nahi jaata. Iski apni qty
    (flux ki recipe qty) aur apni unit (jaise LTR) hoti hai, product ke KG totals me nahi judti. Nahi to None."""
    lines = [l for l in order.lines if l.work_stage_id and l.work_stage_id == stage.work_stage_id]
    if not lines or not all(l.is_flux for l in lines):
        return None
    units = {l.raw_material.base_unit.code if l.raw_material and l.raw_material.base_unit else "KG" for l in lines}
    return {"qty": round(sum(l.required_qty for l in lines), 4), "unit": units.pop() if len(units) == 1 else "KG"}


def stage_unit(order, stage):
    info = side_stage_info(order, stage)
    return info["unit"] if info else "KG"


def main_input(order, stage):
    # Metal chain ka input: pichhle (side nahi) stage ka output; koi nahi to batch KG (Tin + Lead)
    for earlier in reversed([s for s in order.stages if s.sort_order < stage.sort_order]):
        if side_stage_info(order, earlier) is None:
            return earlier.qty_out if earlier.qty_out is not None else order_batch_kg(order)
    return order_batch_kg(order)


def stage_lines(order, stage):
    # Is stage me jaane wali order ki material lines (recipe me jis stage ka material hai)
    return [l for l in order.lines if l.work_stage_id and l.work_stage_id == stage.work_stage_id]


def counts_to_input(line, side):
    # Kaunsi line ki use stage ka input banati hai: flux stage me sab; metal stage me flux ke bina KG wali
    if side:
        return True
    unit = line.raw_material.base_unit.code.upper() if line.raw_material and line.raw_material.base_unit else ""
    return (not line.is_flux) and unit in ("KG", "KGS")


def used_input(order, stage, used_map):
    side = side_stage_info(order, stage)
    total, found = 0.0, False
    for line in stage_lines(order, stage):
        if line.id in used_map and counts_to_input(line, side):
            total += used_map[line.id]
            found = True
    return round(total, 4) if found else None


def _auto_extra_qty(line):
    # Lab correction / complete form se auto-issue hua extra maal (slip "Auto-issue"): ye pakka lagta hai, isliye "used" ka default zaroorat + ye
    total = 0.0
    for issue_line in line.issue_lines:
        issue = issue_line.issue
        if not issue.is_deleted and issue.status == "Posted" and issue.issued_by == "Auto-issue":
            total += issue_line.qty - issue_line.returned_qty
    return total


def stage_material_rows(order, stage):
    # Complete form ke liye: jin lines ka maal production ko mil chuka (issued > 0) unki asli use likhni hai. Issued nahi to puchte nahi
    # (maal baad me issue hua to purana tareeka chalta hai: output par WIP ka saara maal use).
    rows = []
    for line in stage_lines(order, stage):
        if line.issued_qty <= 0.00005:
            continue
        rm = line.raw_material
        rows.append({"id": line.id, "name": rm.name if rm else "", "unit": rm.base_unit.code if rm and rm.base_unit else "",
                     "needed": round(line.required_qty, 4), "spare": line.allowance_qty, "issued": line.issued_qty,
                     "kgpp": line.kg_per_pack if line.is_packing else None,
                     "default": round(min(line.required_qty + _auto_extra_qty(line), line.issued_qty), 4), "counts": counts_to_input(line, side_stage_info(order, stage) is not None)})
    return rows


def stage_plan(order, stage):
    """Is stage me kaunsa material kitna jaata hai, aur batch stage (furnace) ho to kitne lot (client change #6).
    Material = order ki wo lines jinka work_stage_id is stage ka hai. Lot = machine capacity (KG/hr) ke hisaab se, har lot me material
    batch ke hisaab se barabar hissa. Dono khaali ho to None (template kuch nahi dikhata)."""
    lines = [l for l in order.lines if l.work_stage_id and l.work_stage_id == stage.work_stage_id]
    batch_kg = order_batch_kg(order)
    mats = [{"name": l.raw_material.name if l.raw_material else "", "qty": round(l.required_qty, 3),
             "unit": l.raw_material.base_unit.code if l.raw_material and l.raw_material.base_unit else ""} for l in lines]
    lots = []
    cap = stage.capacity_per_hour or 0
    if stage.work_stage and stage.work_stage.is_batch and cap > 0 and batch_kg > 0:
        count = math.ceil(batch_kg / cap - 1e-9)
        left = batch_kg
        for n in range(1, count + 1):
            kg = round(min(cap, left), 3)
            left = round(left - kg, 3)
            lots.append({"n": n, "kg": kg, "mats": [{"name": m["name"], "qty": round(m["qty"] * kg / batch_kg, 3), "unit": m["unit"]} for m in mats]})
    if not mats and not lots:
        return None
    return {"materials": mats, "lots": lots, "lot_kg": cap if lots else None}


def order_summary(order, today):
    """Ek order ka routing haal: stage-wise asli vs plan, progress, kitna late / early, forecast finish.
    delay_days: + = plan se late, - = jaldi. Plan ki dates order ke frozen stage windows se (start_date / end_date)."""
    stages = list(order.stages)
    done = [s for s in stages if s.status == "Done"]
    current = next((s for s in stages if s.status != "Done"), None)
    delay = 0
    last_done = done[-1] if done else None
    if last_done and last_done.completed_at and last_done.end_date:
        delay = (last_done.completed_at.date() - last_done.end_date).days
    if current is not None and current.end_date and today > current.end_date:
        delay = max(delay, (today - current.end_date).days)          # abhi ka stage plan ki aakhri date nikal chuka
    elif current is not None and current.status == "Pending" and current.start_date and today > current.start_date and not done:
        delay = max(delay, (today - current.start_date).days)        # pehla stage start hi nahi hua
    planned_end = order.planned_end_date
    forecast = None
    if planned_end:
        forecast = planned_end + timedelta(days=max(delay, 0))
        forecast = next_working_day(forecast)
    planned_h = sum(s.planned_hours or 0 for s in done)
    actual_h = sum(s.actual_hours or 0 for s in done)
    in_progress = next((s for s in stages if s.status == "In progress"), None)
    return {
        "stages": stages, "done": len(done), "total": len(stages), "current": current, "in_progress": in_progress,
        "all_done": bool(stages) and len(done) == len(stages),
        "pct": int(round(100 * len(done) / len(stages))) if stages else 0,
        "delay": delay, "forecast": forecast, "planned_end": planned_end,
        "planned_h": round(planned_h, 1), "actual_h": round(actual_h, 1),
        "scrap": round(sum(s.scrap_qty or 0 for s in done if side_stage_info(order, s) is None), 2),
        "yield_pct": round(100 * done[-1].qty_out / order_batch_kg(order), 1) if done and done[-1].qty_out and order_batch_kg(order) else None,
    }


def _machine_choices(stage):
    # Is stage ke liye machines: plan wali + usi work stage ki baaki active machines (kharab ho to doosri chalani pade)
    planned_ids = {m.machine_id for m in stage.machines}
    choices = []
    for m in stage.machines:
        choices.append({"id": m.machine_id, "name": m.machine_name, "planned": m.is_planned, "used": m.used})
    others = Machines.query.filter(Machines.work_stage_id == stage.work_stage_id, Machines.is_deleted == False,
                                   Machines.status == "active").order_by(Machines.code).all()
    for m in others:
        if m.id not in planned_ids:
            choices.append({"id": m.id, "name": m.name, "planned": False, "used": False})
    return choices


def lab_lines(order, stage):
    # Lab test form ke "Correction" rows ke liye: is stage ka material (Tin / Lead ...) — kitna chahiye, kitna issue ho chuka
    rows = []
    for line in stage_lines(order, stage):
        rm = line.raw_material
        rows.append({"id": line.id, "name": rm.name if rm else "", "unit": rm.base_unit.code if rm and rm.base_unit else "",
                     "needed": round(line.required_qty, 4), "issued": line.issued_qty})
    return rows


@routing_bp.route("/routing")
def routing_list():
    tab = request.args.get("tab", "running")
    if tab not in ("running", "done"):
        tab = "running"
    today = today_ist()
    orders = (ProductionOrder.query.filter(ProductionOrder.is_deleted == False, ProductionOrder.status == "In production")
              .order_by(ProductionOrder.queue_position, ProductionOrder.id).all())
    summaries = {o.id: order_summary(o, today) for o in orders}
    running = [o for o in orders if summaries[o.id]["stages"] and not summaries[o.id]["all_done"]]
    finished = [o for o in orders if summaries[o.id]["all_done"]]
    shown = running if tab == "running" else finished
    kpi = {"orders": len(running), "active": len([o for o in running if summaries[o.id]["in_progress"]]),
           "late": len([o for o in running if summaries[o.id]["delay"] > 0]), "ready": len(finished)}
    # Drawers ke liye: har stage ka data (JS) — sirf jo abhi kuch kar sakte hain (current stage)
    actions = {}
    for o in shown:
        sm = summaries[o.id]
        cur = sm["current"]
        if cur is None:
            continue
        side = side_stage_info(o, cur)
        qty_in = side["qty"] if side else main_input(o, cur)
        actions[str(cur.id)] = {
            "unit": side["unit"] if side else "KG", "side": bool(side), "materials": stage_material_rows(o, cur),
            "stage_id": cur.id, "order": o.prod_no, "stage": cur.stage_name, "status": cur.status,
            "operator": cur.operator or "", "qty_in": qty_in if side else (cur.qty_in if cur.qty_in is not None else qty_in),
            "planned_hours": cur.planned_hours, "machines": _machine_choices(cur),
            "started_at": cur.started_at.strftime("%d %b %H:%M") if cur.started_at else "",
            "started_iso": cur.started_at.strftime("%Y-%m-%dT%H:%M") if cur.started_at else "",
            "defer_self": bool(cur.work_stage and cur.work_stage.scrap_after_next),
            "defer_prev": None,
            # Ingot Casting jaisa stage: lattha ginti (weight stage master se); Extrusion jaisa stage: scrap box nahi
            "billet": {"weight": cur.work_stage.billet_weight} if cur.work_stage and cur.work_stage.is_billet_stage and not side else None,
            "no_scrap": bool(cur.work_stage and cur.work_stage.no_scrap),
        }
        deferred = deferred_scrap_stage(o, cur)
        if deferred is not None:
            actions[str(cur.id)]["defer_prev"] = {
                "name": deferred.stage_name, "qty_in": deferred.qty_in or 0, "scrap": deferred.scrap_qty or 0,
                "type_id": deferred.scrap_type_id or "", "kind": deferred.scrap_kind or "Saleable",
            }
    operators = [r[0] for r in db.session.query(ProductionOrderStage.operator).filter(ProductionOrderStage.operator.isnot(None)).distinct().order_by(ProductionOrderStage.operator).all()]
    return render_template(
        "routing.html", active_nav="routing", tab=tab, orders=shown, summaries=summaries, kpi=kpi, actions=actions,
        scrap_types=[{"id": t.id, "name": t.name} for t in ScrapType.query.filter_by(is_deleted=False, is_active=True).order_by(ScrapType.name).all()],
        operators=operators, stage_unit=stage_unit, lab_lines=lab_lines, running_count=len(running), done_count=len(finished), today=today, stage_plan=stage_plan, lab_qc_passed=lab_qc_passed,
        now=now_ist().strftime("%Y-%m-%dT%H:%M"),
    )


def _read_when(field):
    # <input type="datetime-local"> ki value -> naive IST datetime; khaali ho to abhi. (value, error)
    raw = (request.form.get(field) or "").strip()
    if not raw:
        return now_ist().replace(second=0, microsecond=0), None
    try:
        value = datetime.strptime(raw, "%Y-%m-%dT%H:%M")
    except ValueError:
        return None, "Enter a valid date and time."
    if value > now_ist() + timedelta(minutes=5):
        return None, "The time cannot be in the future."
    return value, None


def _stage_for_action(stage_id):
    stage = db.session.get(ProductionOrderStage, stage_id)
    if stage is None:
        return None, None, "Stage not found."
    order = stage.production_order
    if order is None or order.is_deleted or order.status != "In production":
        return None, None, "Routing can be updated only for an order that is in production."
    return stage, order, None


def _previous_stages(order, stage):
    return [s for s in order.stages if s.sort_order < stage.sort_order]


def deferred_scrap_stage(order, stage):
    # Is stage se theek pehle ka Done stage agar "scrap baad me" wala hai (Melting) to wahi; warna None
    previous = _previous_stages(order, stage)
    if previous and previous[-1].status == "Done" and previous[-1].work_stage and previous[-1].work_stage.scrap_after_next:
        return previous[-1]
    return None


@routing_bp.route("/routing/start/<int:stage_id>", methods=["POST"])
def routing_start(stage_id):
    stage, order, error = _stage_for_action(stage_id)
    if error:
        flash(error, "error")
        return _back()
    if stage.status != "Pending":
        flash(f"{stage.stage_name} has already been started.", "error")
        return _back()
    previous = _previous_stages(order, stage)
    not_done = [s.stage_name for s in previous if s.status != "Done"]
    if not_done:
        flash(f"Finish {not_done[0]} first. Stages run one after another.", "error")
        return _back()
    blocker = lab_qc_blocker(order, stage)
    if blocker is not None:
        flash(f"{stage.stage_name} cannot start yet: {blocker.stage_name} needs a passed lab test with the test certificate (TC) uploaded first.", "error")
        return _back()
    operator = (request.form.get("operator") or "").strip()[:60]
    if not operator:
        flash("Enter the operator's name.", "error")
        return _back()
    started_at, error = _read_when("started_at")
    if error:
        flash(error, "error")
        return _back()
    if previous and previous[-1].completed_at and started_at < previous[-1].completed_at:
        flash(f"{stage.stage_name} cannot start before {previous[-1].stage_name} finished ({previous[-1].completed_at.strftime('%d %b %H:%M')}).", "error")
        return _back()
    stage.status = "In progress"
    stage.started_at = started_at
    stage.operator = operator
    side = side_stage_info(order, stage)
    stage.qty_in = side["qty"] if side else main_input(order, stage)       # flux stage: flux ki apni qty; baaki: metal chain
    stage.notes = (request.form.get("notes") or "").strip()[:255] or None
    db.session.commit()
    flash(f"{stage.stage_name} started for {order.prod_no}.", "success")
    return _back()


@routing_bp.route("/routing/complete/<int:stage_id>", methods=["POST"])
def routing_complete(stage_id):
    stage, order, error = _stage_for_action(stage_id)
    if error:
        flash(error, "error")
        return _back()
    if stage.status != "In progress":
        flash(f"{stage.stage_name} is not running. Start it first.", "error")
        return _back()
    completed_at, error = _read_when("completed_at")
    if error:
        flash(error, "error")
        return _back()
    if completed_at < stage.started_at:
        flash("The finish time cannot be before the start time.", "error")
        return _back()
    # Single-entry scrap (client change 8): operator sirf scrap likhta hai, good output = aaya hua maal - scrap system nikaalta hai
    # (form ka purana qty_out field ab ignore hota hai — ek hi jagah se number aaye taaki in/out/scrap kabhi na ladein)
    scrap = request.form.get("scrap_qty", type=float) or 0.0
    side = side_stage_info(order, stage)
    unit = side["unit"] if side else "KG"
    qty_in = side["qty"] if side else (stage.qty_in or 0)          # flux stage: hamesha flux ki qty (purane galat 1500 par nahi)
    if scrap < 0:
        flash("Scrap cannot be negative.", "error")
        return _back()
    # "Scrap baad me" wala stage (Melting): uska apna scrap yahan nahi, agle stage (Casting) ke complete par likha jaata hai
    if stage.work_stage and stage.work_stage.scrap_after_next:
        scrap = 0.0
    # Extrusion / Wire Drawing jaisa stage: scrap hota hi nahi (Work Stage master me "No scrap") — form me kuch aaye to bhi 0
    if stage.work_stage and stage.work_stage.no_scrap:
        scrap = 0.0
    # Pichhla stage (Melting) ka scrap abhi likhna hai: kadhai molds me khali ho chuki, ab dross / slag pata hai
    deferred = deferred_scrap_stage(order, stage)
    # Billet (lattha) wala stage (Ingot Casting, client meeting 2 #13): operator lattha ginta hai, scrap = aaya maal - lattha x weight apne aap
    billet = None
    if stage.work_stage and stage.work_stage.is_billet_stage and not side:
        try:
            billet_weight = float((request.form.get("billet_weight") or "").strip())
            billet_count = int(float((request.form.get("billet_count") or "").strip()))
        except ValueError:
            billet_weight, billet_count = 0.0, 0
        if billet_weight <= 0 or billet_count <= 0:
            flash("Enter the billet weight (KG) and how many billets were made.", "error")
            return _back()
        base_in = (deferred.qty_in or 0) if deferred is not None else (stage.qty_in or 0)
        made = round(billet_count * billet_weight, 4)
        if made > base_in + EPS:
            flash(f"{billet_count} billets x {billet_weight:g} KG = {made:g} KG is more than the {base_in:g} KG that came in. Check the count or the billet weight.", "error")
            return _back()
        billet = {"weight": billet_weight, "count": billet_count, "scrap": round(max(base_in - made, 0.0), 4), "photo": None}
        if billet["scrap"] > EPS:
            # Chori / gadbad rokne ke liye: auto nikle scrap ka proof photo zaroori
            photo = request.files.get("scrap_photo")
            if not photo or not photo.filename:
                flash(f"Scrap of {billet['scrap']:g} KG came out of the billet count. Upload a proof photo of the scrap.", "error")
                return _back()
            photo_ext = photo.filename.rsplit(".", 1)[1].lower() if "." in photo.filename else ""
            if photo_ext not in ALLOWED_PHOTO_EXT:
                flash("The proof must be a PNG, JPG or WEBP photo.", "error")
                return _back()
            photo.stream.seek(0, os.SEEK_END)
            photo_size = photo.stream.tell()
            photo.stream.seek(0)
            if photo_size > MAX_TC_BYTES:
                flash("The proof photo is too large (maximum 5 MB).", "error")
                return _back()
            billet["photo"] = photo
        if deferred is None:
            scrap = billet["scrap"]
    prev_scrap = 0.0
    prev_type = None
    prev_kind = "Saleable"
    if deferred is not None:
        prev_scrap = billet["scrap"] if billet else (request.form.get("prev_scrap_qty", type=float) or 0.0)
        if prev_scrap < 0:
            flash("Scrap cannot be negative.", "error")
            return _back()
        if prev_scrap > (deferred.qty_in or 0) + EPS:
            flash(f"{deferred.stage_name} scrap ({prev_scrap:g}) cannot be more than what came into {deferred.stage_name} ({(deferred.qty_in or 0):g} KG).", "error")
            return _back()
        if prev_scrap > 0:
            # Billet stage me type / kind wahi standard fields se aate hain (scrap box ek hi hai); warna "pichhle stage ka scrap" wale fields se
            kind_field, type_field = ("scrap_kind", "scrap_type_id") if billet else ("prev_scrap_kind", "prev_scrap_type_id")
            prev_kind = (request.form.get(kind_field) or "Saleable").strip()
            if prev_kind not in ("Saleable", "Process loss"):
                flash("Choose whether the scrap is saleable or a process loss.", "error")
                return _back()
            prev_type_id = request.form.get(type_field, type=int)
            prev_type = db.session.get(ScrapType, prev_type_id) if prev_type_id else None
            if prev_type is None or prev_type.is_deleted or not prev_type.is_active:
                flash(f"Choose the type of the {deferred.stage_name} scrap.", "error")
                return _back()
        # Casting me aane wala maal = Melting me gaya maal - Melting ka scrap
        qty_in = round((deferred.qty_in or 0) - prev_scrap, 4)
    # RM used (ek hi baar, rounds nahi): jin lines ka maal issue ho chuka unki asli use. Field na aaye to purana tareeka (use None).
    used_map = {}
    extra_issues = []         # (packing line, kitna extra, kisne liya, reason) — validation ke baad hi store se issue hote hain
    for line in stage_lines(order, stage):
        raw = request.form.get(f"used_{line.id}")
        if raw is None or raw.strip() == "":
            continue
        try:
            used = float(raw)
        except ValueError:
            flash("Enter a valid quantity for the raw material used.", "error")
            return _back()
        name = line.raw_material.name if line.raw_material else "Material"
        mat_unit = line.raw_material.base_unit.code if line.raw_material and line.raw_material.base_unit else ""
        if used < 0:
            flash(f"{name}: the quantity used cannot be negative.", "error")
            return _back()
        if used > line.issued_qty + EPS:
            # Jyada laga (spool 520 bane / metal correction me zyada gaya): store se ek click me extra issue, kisne liya uska naam zaroori
            # (client meeting 2, #14 spool, #12 sab material). Koi % cap nahi.
            taken_by = (request.form.get(f"extra_by_{line.id}") or "").strip()[:60]
            if not taken_by:
                flash(f"{name}: {used:g} {mat_unit} used but only {line.issued_qty:g} {mat_unit} were issued. Write who took the extra {round(used - line.issued_qty, 4):g} {mat_unit} from the store.", "error")
                return _back()
            reason = (request.form.get(f"extra_reason_{line.id}") or "").strip()[:200] or "More used than issued"
            extra_issues.append((line, round(used - line.issued_qty, 4), taken_by, reason))
        used_map[line.id] = round(used, 4)
    work_hours = None
    hours_raw = (request.form.get("work_hours") or "").strip()
    if hours_raw:
        try:
            work_hours = float(hours_raw)
        except ValueError:
            work_hours = -1
        if work_hours < 0 or work_hours > 2000:
            flash("Enter the working hours as a number (for example 6.5).", "error")
            return _back()
    # Output "used" ke hisaab se: is stage ka input = asli use hua maal (flux stage me flux, metal stage me Tin + Lead KG). Phir usme se scrap minus.
    eff_in = used_input(order, stage, used_map)
    if eff_in is not None and deferred is None:
        qty_in = eff_in
    if scrap > qty_in + EPS:
        flash(f"Scrap ({scrap:g}) cannot be more than what came into this stage ({qty_in:g} {unit}).", "error")
        return _back()
    qty_out = max(qty_in - scrap, 0.0)
    if qty_out <= EPS:
        flash("Scrap cannot be the whole quantity. Some material must go on to the next stage.", "error")
        return _back()
    # Scrap hui to batao kis tarah ka aur kaisa (Saleable = Scrap warehouse me jaayega, Process loss = sirf record)
    scrap_type = None
    scrap_kind = "Saleable"
    if scrap > 0:
        scrap_kind = "Process loss" if side else (request.form.get("scrap_kind") or "Saleable").strip()      # flux ka waste stock nahi banta
        if scrap_kind not in ("Saleable", "Process loss"):
            flash("Choose whether the scrap is saleable or a process loss.", "error")
            return _back()
        type_id = request.form.get("scrap_type_id", type=int)
        scrap_type = db.session.get(ScrapType, type_id) if type_id else None
        if scrap_type is None or scrap_type.is_deleted or not scrap_type.is_active:
            flash("Choose the scrap type.", "error")
            return _back()
    # Machines jo asli me chali: plan wali + usi work stage ki koi bhi active machine
    ids = {int(x) for x in request.form.getlist("machine_ids") if x.isdigit()}
    if not ids:
        flash("Tick at least one machine that was used.", "error")
        return _back()
    planned = {m.machine_id: m for m in stage.machines}
    extra = []
    for machine_id in ids:
        if machine_id in planned:
            continue
        machine = db.session.get(Machines, machine_id)
        if machine is None or machine.is_deleted or machine.status != "active" or machine.work_stage_id != stage.work_stage_id:
            flash("A chosen machine does not belong to this stage.", "error")
            return _back()
        extra.append(machine)
    for machine_id, row in planned.items():
        row.used = machine_id in ids
    for machine in extra:
        db.session.add(ProductionOrderStageMachine(stage_id=stage.id, machine_id=machine.id, machine_name=machine.name,
                                                   capacity_per_hour=machine.capacity_per_hour or 0, hours_per_day=machine.hours_per_day or 8,
                                                   is_planned=False, used=True))
    # Jyada bane packing (spool / box) ka extra maal store se auto-issue: store me kam ho to kuch save nahi hota
    if extra_issues:
        from app.inventory.posting import InventoryError
        from app.material_issues.routes import auto_issue_extra
        for line, extra_qty, taken_by, reason in extra_issues:
            try:
                auto_issue_extra(order, line, extra_qty, taken_by, f"Auto-issued at {stage.stage_name}: {reason}")
            except InventoryError as stock_error:
                db.session.rollback()
                flash(str(stock_error), "error")
                return _back()
    operator = (request.form.get("operator") or "").strip()[:60]
    if operator:
        stage.operator = operator
    if deferred is not None:
        # Melting stage ka scrap + uska qty_out ab pakka; Casting ka qty_in bhi usi hisaab se
        deferred.scrap_qty = round(prev_scrap, 4)
        deferred.scrap_type_id = prev_type.id if prev_type else None
        deferred.scrap_kind = prev_kind
        deferred.qty_out = round(qty_in, 4)
        stage.qty_in = round(qty_in, 4)
    if side or (eff_in is not None and deferred is None):
        stage.qty_in = round(qty_in, 4)
    for line in stage_lines(order, stage):
        if line.id in used_map:
            line.used_qty = used_map[line.id]
    stage.work_hours = round(work_hours, 2) if work_hours is not None else None
    if billet is not None:
        # Lattha ginti ka record + proof photo (uploads/scrap_proof/<stage id>/); billet weight stage master me default ban jaata hai
        stage.billet_count = billet["count"]
        stage.billet_weight = billet["weight"]
        stage.scrap_photo = None
        if billet["photo"] is not None:
            folder = os.path.join(current_app.config["UPLOAD_FOLDER"], "scrap_proof", str(stage.id))
            os.makedirs(folder, exist_ok=True)
            photo_name = secure_filename(billet["photo"].filename) or "scrap-proof.jpg"
            billet["photo"].save(os.path.join(folder, photo_name))
            stage.scrap_photo = "scrap_proof/" + str(stage.id) + "/" + photo_name          # DB me hamesha "/"
        stage.work_stage.billet_weight = billet["weight"]
    stage.status = "Done"
    stage.completed_at = completed_at
    stage.qty_out = round(qty_out, 4)
    stage.scrap_qty = round(scrap, 4)
    stage.scrap_type_id = scrap_type.id if scrap_type else None
    stage.scrap_kind = scrap_kind
    note = (request.form.get("notes") or "").strip()[:255]
    if note:
        stage.notes = note
    db.session.commit()
    summary = order_summary(order, today_ist())
    if summary["all_done"]:
        flash(f"{stage.stage_name} done. All stages of {order.prod_no} are complete.", "success")
        return _back("done")
    flash(f"{stage.stage_name} done for {order.prod_no}. Next: {summary['current'].stage_name}.", "success")
    return _back()


@routing_bp.route("/routing/reopen/<int:stage_id>", methods=["POST"])
def routing_reopen(stage_id):
    # Galti sudharne ke liye: sirf aakhri Done stage, aur tab jab agla stage shuru na hua ho
    stage, order, error = _stage_for_action(stage_id)
    if error:
        flash(error, "error")
        return _back()
    if stage.status != "Done":
        flash("Only a finished stage can be reopened.", "error")
        return _back()
    later = [s for s in order.stages if s.sort_order > stage.sort_order and s.status != "Pending"]
    if later:
        flash(f"{later[0].stage_name} has already started, so {stage.stage_name} cannot be reopened.", "error")
        return _back()
    for row in list(stage.machines):
        if not row.is_planned:
            db.session.delete(row)          # chalte waqt jodi gayi machine hata do; plan wali rehti hain
        else:
            row.used = False
    for line in stage_lines(order, stage):
        line.used_qty = None              # RM use dobara likhi jayegi
    stage.work_hours = None
    stage.billet_count = None
    stage.billet_weight = None
    stage.scrap_photo = None
    stage.status = "In progress"
    stage.completed_at = None
    stage.qty_out = None
    stage.scrap_qty = None
    stage.scrap_type_id = None
    stage.scrap_kind = "Saleable"
    db.session.commit()
    flash(f"{stage.stage_name} reopened. Enter the finish details again.", "success")
    return _back()


# ---------------------------------------------------------------- Lab QC + TC (client change #7)
ALLOWED_TC_EXT = {"pdf", "png", "jpg", "jpeg"}
ALLOWED_PHOTO_EXT = {"png", "jpg", "jpeg", "webp"}
MAX_TC_BYTES = 5 * 1024 * 1024


def lab_qc_passed(stage):
    # Is stage ka koi Pass round jisme TC file lagi ho
    return any(q.result == "Pass" and q.tc_file for q in stage.lab_qcs)


def lab_qc_blocker(order, stage):
    # Agar is stage se pehle ka koi Lab-QC-wala stage Pass + TC ke bina hai to uska naam (warna None)
    for prev in _previous_stages(order, stage):
        if prev.work_stage and prev.work_stage.requires_lab_qc and not lab_qc_passed(prev):
            return prev
    return None


@routing_bp.route("/routing/lab_qc/<int:stage_id>", methods=["POST"])
def routing_lab_qc(stage_id):
    stage, order, error = _stage_for_action(stage_id)
    if error:
        flash(error, "error")
        return _back()
    if not (stage.work_stage and stage.work_stage.requires_lab_qc):
        flash(f"{stage.stage_name} does not need a lab QC.", "error")
        return _back()
    if stage.status == "Pending":
        flash(f"Start {stage.stage_name} before recording its lab test.", "error")
        return _back()
    tested_by = (request.form.get("tested_by") or "").strip()[:60]
    result = (request.form.get("result") or "").strip()
    remarks = (request.form.get("remarks") or "").strip()[:255] or None
    tested_at, error = _read_when("tested_at")
    if error:
        flash(error, "error")
        return _back()
    if not tested_by:
        flash("Enter who did the lab test.", "error")
        return _back()
    if result not in ("Pass", "Need correction", "Fail"):
        flash("Choose the lab result: Pass, Need correction or Fail.", "error")
        return _back()
    # Correction (client meeting 2, #12): lab ne kaha metal kam / zyada — jo extra metal dala wo yahin likho, store se apne aap issue ho jaata hai.
    # Koi % cap nahi (2% sirf andaza). Naam zaroori; reason na likho to remarks / "Lab correction".
    allowed_lines = {line.id: line for line in stage_lines(order, stage)}
    wanted_extra = {}
    index = 0
    while f"extra_line_{index}" in request.form:
        line_id = request.form.get(f"extra_line_{index}", type=int)
        extra_qty = request.form.get(f"extra_qty_{index}", type=float)
        index += 1
        if not extra_qty:
            continue
        if extra_qty < 0 or line_id not in allowed_lines:
            flash("Choose a material of this stage and a quantity above zero for the correction.", "error")
            return _back()
        wanted_extra[line_id] = round(wanted_extra.get(line_id, 0) + extra_qty, 4)
    added_by = (request.form.get("extra_by") or "").strip()[:60]
    if wanted_extra and not added_by:
        flash("Write who added the extra material.", "error")
        return _back()
    extra_reason = (request.form.get("extra_reason") or "").strip()[:200] or remarks or "Lab correction"
    tc = request.files.get("tc_file")
    has_file = bool(tc and tc.filename)
    if result == "Pass" and not has_file:
        flash("Upload the test certificate (TC) — a passed lab test needs it before the next stage can start.", "error")
        return _back()
    ext = tc.filename.rsplit(".", 1)[1].lower() if has_file and "." in tc.filename else ""
    if has_file:
        if ext not in ALLOWED_TC_EXT:
            flash("The test certificate must be a PDF, PNG or JPG file.", "error")
            return _back()
        tc.stream.seek(0, os.SEEK_END)
        size = tc.stream.tell()
        tc.stream.seek(0)
        if size > MAX_TC_BYTES:
            flash("The test certificate file is too large (maximum 5 MB).", "error")
            return _back()
    corrections = []
    if wanted_extra:
        from app.inventory.posting import InventoryError
        from app.material_issues.routes import auto_issue_extra
        for line_id, extra_qty in wanted_extra.items():
            line = allowed_lines[line_id]
            try:
                issue = auto_issue_extra(order, line, extra_qty, added_by, f"Lab correction at {stage.stage_name}: {extra_reason}")
            except InventoryError as stock_error:
                db.session.rollback()
                flash(str(stock_error), "error")
                return _back()
            rm = line.raw_material
            corrections.append({"material": rm.name if rm else "", "qty": extra_qty, "unit": rm.base_unit.code if rm and rm.base_unit else "",
                                "added_by": added_by, "reason": extra_reason, "issue_no": issue.issue_no})
    row = StageLabQC(stage_id=stage.id, tested_at=tested_at, tested_by=tested_by, result=result, remarks=remarks, corrections=corrections or None)
    db.session.add(row)
    db.session.flush()                      # id chahiye: file ka folder QC id se banta hai
    if has_file:
        folder = os.path.join(current_app.config["UPLOAD_FOLDER"], "lab_qc", str(row.id))
        os.makedirs(folder, exist_ok=True)
        name = secure_filename(tc.filename) or ("tc." + ext)
        tc.save(os.path.join(folder, name))
        row.tc_file = "lab_qc/" + str(row.id) + "/" + name         # DB me hamesha "/"
    db.session.commit()
    added_text = (" Extra issued from the store: " + ", ".join(f"{c['qty']:g} {c['unit']} {c['material']}".replace("  ", " ") for c in corrections) + ".") if corrections else ""
    if result == "Pass":
        flash(f"Lab test passed for {stage.stage_name} ({order.prod_no}) and the TC is saved. The next stage can start.{added_text}", "success")
    elif result == "Need correction":
        flash(f"Lab test for {stage.stage_name} ({order.prod_no}): correction needed.{added_text} Record the next test after the correction.", "success")
    else:
        flash(f"Lab test failed for {stage.stage_name} ({order.prod_no}). Correct the batch and record the next test.{added_text}", "success")
    return _back()


@routing_bp.route("/routing/tc/<int:qc_id>")
def routing_tc(qc_id):
    # Test Certificate file kholna
    row = db.session.get(StageLabQC, qc_id)
    if row is None or not row.tc_file:
        abort(404)
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], row.tc_file)


@routing_bp.route("/routing/scrap_photo/<int:stage_id>")
def routing_scrap_photo(stage_id):
    # Billet (lattha) stage ke scrap ka proof photo kholna
    stage = db.session.get(ProductionOrderStage, stage_id)
    if stage is None or not stage.scrap_photo:
        abort(404)
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], stage.scrap_photo)
