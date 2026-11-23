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
from app.production_orders.stage_material import gap_text, stage_material_gap
from app.routing.pcs import pcs_mode, spools_made, to_pcs
from app.production_orders.scheduler import now_ist, today_ist
from app.routing.batch import combine_error, ensure_melt_group, melt_kg, melt_members, melt_plan, stage_kg
from app.routing.assign import assign_machine, drop_rows, eligible_machines, restore_planned, settle, target_error
from app.routing.busy import busy_machines
from app.routing.handoff import casting_ahead, metal_wait, stage_clash

routing_bp = Blueprint("routing", __name__, template_folder="templates")

EPS = 0.0001


def in_production_orders():
    # Abhi chal rahe (In production) saare orders — stage timing clash dekhne ke liye
    return ProductionOrder.query.filter(ProductionOrder.is_deleted == False, ProductionOrder.status == "In production").all()


def _back(tab="running"):
    return redirect(url_for("routing.routing_list", tab=tab))


def order_batch_kg(order):
    return round(order.planned_qty * order.unit_weight, 4)


def flux_only_order(order):
    # Flux jaise in-house product ka apna order: iski poori recipe flux ki hai, isliye iska stage "side" nahi, ye khud hi metal chain hai
    # (iska output KG me product ka Good maal banta hai). Wire ke order me flux ek side stage / line hoti hai.
    main = [l for l in order.lines if not l.is_packing and not l.is_extra]
    return bool(main) and all(l.is_flux for l in main)


def side_stage_info(order, stage):
    """Flux Preparation jaisa "side" stage: iski saari material lines flux ki hon to iska maal metal chain me nahi jaata. Iski apni qty
    (flux ki recipe qty) aur apni unit (jaise LTR) hoti hai, product ke KG totals me nahi judti. Nahi to None."""
    lines = [l for l in order.lines if l.work_stage_id and l.work_stage_id == stage.work_stage_id]
    if not lines or not all(l.is_flux for l in lines) or flux_only_order(order):
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
    return (not line.is_flux or flux_only_order(line.production_order)) and unit in ("KG", "KGS")


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
    # C9 phase 2: combined melt me furnace ke lot poore melt (sab orders) ke KG par bante hain; akele order me melt_kg = order ka KG
    is_melt_stage = bool(stage.work_stage and stage.work_stage.is_batch and side_stage_info(order, stage) is None)
    batch_kg = melt_kg(stage) if is_melt_stage else order_batch_kg(order)
    combined = is_melt_stage and len(melt_members(stage)) > 1
    mats = [{"name": l.raw_material.name if l.raw_material else "", "qty": round(l.required_qty, 3),
             "unit": l.raw_material.base_unit.code if l.raw_material and l.raw_material.base_unit else ""} for l in lines]
    lots = []
    cap = stage.capacity_per_hour or 0
    lot_hours = None
    mp = melt_plan(order, stage, batch_kg)          # C8a: machine me batch capacity bhari ho to lot = wahi (aur har lot ke ghante)
    if mp is not None:
        cap, lot_hours = mp["cap"], mp["hours"]
    if stage.work_stage and stage.work_stage.is_batch and cap > 0 and batch_kg > 0:
        count = math.ceil(batch_kg / cap - 1e-9)
        left = batch_kg
        for n in range(1, count + 1):
            kg = round(min(cap, left), 3)
            left = round(left - kg, 3)
            # Combined melt me ek lot me kai orders ka maal hota hai — lot ke andar ka material order-wise yahan nahi dikhate
            lots.append({"n": n, "kg": kg, "mats": [] if combined else [{"name": m["name"], "qty": round(m["qty"] * kg / batch_kg, 3), "unit": m["unit"]} for m in mats]})
    if not mats and not lots:
        return None
    return {"materials": mats, "lots": lots, "lot_kg": cap if lots else None, "lot_hours": lot_hours,
            "unused_kg": mp["unused_kg"] if mp else 0, "suggest": mp["suggest"] if mp else [], "melt": melt_info(order, stage) if is_melt_stage else None}


def melt_info(order, stage):
    """C9 phase 2: Melting stage ke liye melt (heat number) ki jaankari: heat no, members, aur jo orders abhi jud sakte hain.
    can_edit = melt shuru nahi hua (sab members Pending) aur ye stage Pending."""
    members = melt_members(stage)
    started = any(m.status != "Pending" for m in members)
    info = {"heat_no": stage.melt_group.heat_no if stage.melt_group_id else None, "started": started,
            "members": [{"stage_id": m.id, "prod_no": m.production_order.prod_no, "kg": stage_kg(m), "me": m.id == stage.id} for m in members],
            "total_kg": melt_kg(stage), "can_edit": False, "candidates": [], "others": []}
    if started or stage.status != "Pending":
        return info
    info["can_edit"] = True
    plan = melt_plan(order, stage, melt_kg(stage))
    if plan is not None:
        info["candidates"] = [s for s in plan["suggest"] if s["in_production"]]
        info["others"] = [s for s in plan["suggest"] if not s["in_production"]]
    return info


def _member_start_problem(member):
    # Combined melt ke doosre member ka Start rukne ka kaaran (text) ya None. Wahi shartein jo akele stage par lagti hain.
    order = member.production_order
    if order is None or order.is_deleted or order.status != "In production":
        return "is not in production."
    if member.status != "Pending":
        return "has already started."
    not_done = [s.stage_name for s in _previous_stages(order, member) if s.status != "Done"]
    if not_done:
        return f"has not finished {not_done[0]} yet."
    gaps = stage_material_gap(order, member.work_stage_id)
    if gaps:
        return f"does not have its material fully issued ({gap_text(gaps)})."
    if lab_qc_blocker(order, member) is not None:
        return "is waiting for an earlier lab test."
    return None


def waste_payload(mp):
    # C8a: melt_plan ka JS ke liye rup; furnace poori bhar rahi ho (unused 0) to None
    if mp is None or mp["unused_kg"] <= 0.0005:
        return None
    return {"cap": mp["cap"], "melts": len(mp["lots"]), "unused": mp["unused_kg"], "machine": mp["machine"], "suggest": mp["suggest"]}


def wait_payload(wait):
    # C12: metal_wait ka JS ke liye saaf rup (datetime nahi, text). None = kuch dikhana nahi.
    if wait is None:
        return None
    return {"since": wait["since"].strftime("%H:%M" if wait["since"].date() == now_ist().date() else "%d %b %H:%M"), "minutes": round(wait["minutes"]),
            "limit": wait["limit"], "over": wait["over"], "prev": wait["prev_name"]}


def cast_payload(cast):
    # G14-4: casting_ahead ka JS ke liye saaf rup. None = kuch dikhana nahi.
    if cast is None:
        return None
    return {"text": cast["message"], "needs_reason": cast["needs_reason"]}


def pcs_cells(order, stage):
    """C15: stage table ke liye PCS rup: None (KG hi) ya {"kind", "in", "out", "scrap"} (PCS me). Spooling (kind "out") me wire KG hi aata hai,
    nikalti hai spool ki ginti (jo operator ne likhi, nahi to KG / nominal weight). Baad ke stages me in / out / scrap sab PCS."""
    if side_stage_info(order, stage) is not None:
        return None
    pm = pcs_mode(order, stage)
    if pm is None or stage.qty_out is None:
        return None
    if pm["kind"] == "out":
        made = spools_made(order, stage)
        return {"kind": "out", "out": made if made is not None else to_pcs(stage.qty_out, pm), "scrap": None, "in": None}
    return {"kind": "all", "in": to_pcs(stage.qty_in, pm), "out": to_pcs(stage.qty_out, pm), "scrap": to_pcs(stage.scrap_qty, pm) if stage.scrap_qty else 0}


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
    on_hold = next((s for s in stages if s.status == "On hold"), None)
    return {
        "stages": stages, "done": len(done), "total": len(stages), "current": current, "in_progress": in_progress, "on_hold": on_hold,
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


# G27: machine ka status text (Machine master me Active / Maintenance / Breakdown / Retired)
MACHINE_STATUS_TEXT = {"breakdown": "under breakdown", "maintenance": "under maintenance", "retired": "retired"}


def stage_machine_problem(stage):
    """Is stage ki chuni hui machines me se jo Active nahi (breakdown / maintenance / retired / deleted) unki jaankari.
    None = sab theek. Warna {"names": "Furnace 2 (under breakdown)", "all_down": sab ki sab kharab?, "swaps": usi work stage ki Active machines jo is stage me nahi, "rows": [(row, machine)]}.
    all_down hone par stage Start nahi hota jab tak doosri machine na chuni jaye; kuch hi kharab ho to unhe hata kar baaki se chalta hai."""
    rows = list(stage.machines)
    # C8 / C11: Pending stage ki machine par doosre order ka stage abhi chal raha ho to wo bhi "available nahi" (busy) gini jaati hai
    busy = busy_machines(stage.production_order, stage) if stage.status == "Pending" else {}
    down = []
    reasons = []
    for row in rows:
        machine = db.session.get(Machines, row.machine_id)
        if machine is not None and (machine.is_deleted or machine.status != "active"):
            down.append((row, machine))
            reasons.append(f"{machine.name} ({MACHINE_STATUS_TEXT.get(machine.status, 'not available')})")
        elif machine is not None and row.machine_id in busy:
            down.append((row, machine))
            reasons.append(f"{machine.name} ({busy[row.machine_id]['text']})")
    if not down:
        return None
    return {"names": ", ".join(reasons),
            "all_down": len(down) == len(rows),
            # Badli machine: usi work stage ki Active machine jo plan me nahi, abhi khali (busy nahi) hai aur jiski line chal rahi hai (D6)
            "swaps": [{"id": m.id, "name": m.name, "line": m.line.name if m.line else ""} for m in eligible_machines(stage.production_order, stage, busy)],
            "rows": down}


def lab_lines(order, stage):
    # Lab test form ke "Correction" rows ke liye: is stage ka material (Tin / Lead ...) — kitna chahiye, kitna issue ho chuka
    rows = []
    for line in stage_lines(order, stage):
        rm = line.raw_material
        rows.append({"id": line.id, "name": rm.name if rm else "", "unit": rm.base_unit.code if rm and rm.base_unit else "",
                     "needed": round(line.required_qty, 4), "issued": line.issued_qty})
    return rows


def next_on_machine(done_stage):
    """Stage Complete hone ke baad: jin machines par wo chala unki queue me sabse pehle kaun sa order ab shuru ho sakta hai (client meeting 2, #11).
    Sirf wahi order jiska agla (pehla na-hua) stage isi machine par hai — baad ke stage ko abhi shuru nahi kar sakte. Dusre order ki hi baat (apna agla stage nahi).
    Wapas dict (order, stage, machine_name, status) ya None."""
    from app.dashboard.routes import queue_by_machine          # yahin import: dashboard.routes khud routing se juda nahi, par load-order ke jhanjhat se bachne ke liye
    own = done_stage.production_order
    machine_ids = [row.machine_id for row in done_stage.machines if row.used] or [row.machine_id for row in done_stage.machines]
    queue = queue_by_machine(today_ist())
    candidates = []
    for machine_id in machine_ids:
        for q in queue.get(machine_id, []):
            if q["order_id"] == own.id:
                continue
            stage = db.session.get(ProductionOrderStage, q["stage_id"])
            order = stage.production_order if stage else None
            if order is None or stage.status != "Pending":
                continue
            first_open = next((s for s in order.stages if s.status != "Done"), None)
            if first_open is None or first_open.id != stage.id:
                continue
            machine = db.session.get(Machines, machine_id)
            if machine is None or machine.status != "active":
                continue
            candidates.append(((q["position"] if q["position"] is not None else 10 ** 9, q["prod_no"]),
                               {"order": order, "stage": stage, "machine_name": machine.name, "status": order.status}))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


@routing_bp.route("/routing")
def routing_list():
    tab = request.args.get("tab", "running")
    if tab not in ("running", "done"):
        tab = "running"
    # "Next on this machine" box: Complete ke baad ?after=<khatam hua stage id>; ?focus=<stage id> us stage ka card chamkata hai
    next_up = None
    after_id = request.args.get("after", type=int)
    if after_id:
        done_stage = db.session.get(ProductionOrderStage, after_id)
        if done_stage is not None and done_stage.status == "Done":
            next_up = next_on_machine(done_stage)
    focus_id = request.args.get("focus", type=int)
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
    material_alerts = {}         # {stage id: text} — C7: card par "material not fully issued" alert
    machine_alerts = {}          # {stage id: text} — card par laal "machine not working" line (G27)
    # C14: stage ke baad jo maal bacha (issued - used) uska chhota text, card par "return to store" chip ke liye
    from app.material_issues.routes import leftover_items
    leftover_text = {}
    for o in shown:
        items = leftover_items(o)
        if items:
            leftover_text[o.id] = ", ".join(f"{i['qty']:g} {i['unit']} {i['name']}".strip() for i in items)
    clash_orders = in_production_orders()
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
            "hold_min": round(cur.hold_minutes or 0, 1), "hold_reason": cur.hold_reason or "",
            "held_at": cur.held_at.strftime("%d %b %H:%M") if cur.held_at else "",
            "defer_self": bool(cur.work_stage and cur.work_stage.scrap_after_next),
            "defer_prev": None,
            # fix_list #4: pichhle stage ke lab test me jo extra metal dala wo is stage ke input me juda hai — "includes 0.5 KG correction"
            "corr_in": (correction_in(o, cur) or {}).get("text") if side is None else None,
            # Ingot Casting jaisa stage: lattha ginti (weight stage master se); Extrusion jaisa stage: scrap box nahi
            "billet": {"weight": cur.work_stage.billet_weight} if cur.work_stage and cur.work_stage.is_billet_stage and not side else None,
            "no_scrap": bool(cur.work_stage and cur.work_stage.no_scrap),
            # C15: Spooling (kind "out") / uske baad ke stages (kind "all") PCS rup me; wa = asli KG per piece. Side stage (flux) me nahi.
            "pcs": ({"kind": pm["kind"], "w": pm["w"], "wa": pm["wa"]} if (pm := (None if side else pcs_mode(o, cur))) else None),
            # Stage timing clash lock: shuru karne par kisi doosre order ke garam maal se takrao ho to uska message (start drawer me dikhta hai)
            "clash": (stage_clash(o, cur, clash_orders) or {}).get("message") if cur.status == "Pending" else None,
            # C12: Melting ke baad garam maal kab se ruka hai (Work Stage me limit bhari ho to); limit paar ho to Start par wajah likhni padti hai
            "wait": wait_payload(metal_wait(o, cur)),
            # G14-4: Melting Start par — melt taiyar hone par Casting machine free hogi? Nahi to message (aur limit se zyada ho to wajah zaroori)
            "cast": cast_payload(casting_ahead(o, cur)) if side is None else None,
            # C8a: furnace poori nahi bhar rahi (capacity waste) — Melting Start par wajah likhni padti hai; suggestion me same-alloy orders
            "waste": waste_payload(melt_plan(o, cur, melt_kg(cur))) if cur.status == "Pending" and side is None else None,
            "heat": ({"no": cur.melt_group.heat_no, "orders": [m.production_order.prod_no for m in melt_members(cur)]}
                     if cur.melt_group_id and len(melt_members(cur)) > 1 else None),
        }
        # C7: Pending stage ka maal poora issue nahi hua to card par laal alert (Start tab tak block rehta hai)
        if cur.status == "Pending":
            gaps = stage_material_gap(o, cur.work_stage_id)
            if gaps:
                material_alerts[cur.id] = gap_text(gaps)
        # G27: stage ki machine kharab / maintenance me ho to Start drawer me "Use this machine instead" aur card par laal alert
        problem = stage_machine_problem(cur)
        if problem is not None:
            actions[str(cur.id)]["down"] = {"names": problem["names"], "all_down": problem["all_down"], "swaps": problem["swaps"]} if cur.status == "Pending" else None
            if cur.status == "Pending":
                machine_alerts[cur.id] = (f"{problem['names']}. " + ("Choose another machine when you start this stage." if problem["all_down"]
                                          else "It will be left out when you start this stage."))
            else:
                machine_alerts[cur.id] = f"{problem['names']}. Hold the stage if work has stopped, and when you complete it tick the machine that was really used."
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
        operators=operators, stage_unit=stage_unit, lab_lines=lab_lines, running_count=len(running), done_count=len(finished), today=today, stage_plan=stage_plan, lab_qc_passed=lab_qc_passed, lab_qc_blocker=lab_qc_blocker,
        now=now_ist().strftime("%Y-%m-%dT%H:%M"), pcs_cells=pcs_cells, wait_payload=wait_payload, metal_wait=metal_wait, next_up=next_up, focus_id=focus_id, machine_alerts=machine_alerts, material_alerts=material_alerts, leftover_text=leftover_text,
    )


def _read_when(field, form=None):
    # <input type="datetime-local"> ki value -> naive IST datetime; khaali ho to abhi. (value, error)
    # form=None to request.form; Dashboard ka Assign & Start apna form de sakta hai (start_stage ke saath wahi function chalta hai)
    form = request.form if form is None else form
    raw = (form.get(field) or "").strip()
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


def next_main_stage(order, stage):
    # Metal chain me is stage ke baad ka agla (side nahi) stage; koi nahi to None
    for later in order.stages:
        if later.sort_order > stage.sort_order and side_stage_info(order, later) is None:
            return later
    return None


def correction_in(order, stage):
    """fix_list #4: pichhle metal stage ke lab test me jo extra metal (KG) dala gaya, wo is stage ke "Came into this stage" me already juda hai —
    sirf dikhane ke liye {"qty", "stage", "text"} (ya None)."""
    previous = None
    for earlier in order.stages:
        if earlier.sort_order < stage.sort_order and side_stage_info(order, earlier) is None:
            previous = earlier
    if previous is None:
        return None
    total, names = 0.0, []
    for qc in previous.lab_qcs:
        for item in (qc.corrections or []):
            # purani entries me "in_input" key nahi hoti (default: judta hai); nayi me False ho to (flux wali) dikhana nahi
            if str(item.get("unit", "")).upper() in ("KG", "KGS") and item.get("in_input", True):
                total += float(item.get("qty") or 0)
                if item.get("material") and item["material"] not in names:
                    names.append(item["material"])
    if total <= EPS:
        return None
    return {"qty": round(total, 4), "stage": previous.stage_name, "text": f"includes {total:g} KG correction ({', '.join(names)}) added at {previous.stage_name}"}


def deferred_scrap_stage(order, stage):
    # Is stage se theek pehle ka Done stage agar "scrap baad me" wala hai (Melting) to wahi; warna None
    previous = _previous_stages(order, stage)
    if previous and previous[-1].status == "Done" and previous[-1].work_stage and previous[-1].work_stage.scrap_after_next:
        return previous[-1]
    return None


def start_stage(stage, order, form, target_machine_id=None, kind="swap", assigned_note=""):
    """Stage ka Start — saare gates ek jagah (Routing page aur Dashboard "Assign & Start" dono yahi chalate hain, koi gate bypass nahi hota).
    Wapas (True, "success text") ya (False, "error text"). COMMIT NAHI karta aur flash nahi karta: caller commit kare; fail ho to caller db.session.rollback()
    kare (kyunki machine badalne jaise changes fail hone se pehle session me ho chuke ho sakte hain).
    target_machine_id: is machine par chalao (plan wali machine ki jagah) — Dashboard ka "Assign & Start". Khaali ho to purana tareeka: plan wali machine,
    aur sab ki sab kharab / busy ho to form ka swap_machine_id. kind: log me "assign" (Dashboard) ya "swap" (Routing page).
    assigned_note: caller ne machine pehle hi badal di ho (Released order: schedule naye machine ke hisaab se bane) to stage notes me jaane wala text."""
    if stage.status != "Pending":
        return False, f"{stage.stage_name} has already been started."
    previous = _previous_stages(order, stage)
    not_done = [s.stage_name for s in previous if s.status != "Done"]
    if not_done:
        return False, f"Finish {not_done[0]} first. Stages run one after another."
    # C7: is stage ka maal (recipe me jo isi stage ke saamne hai) poora issue hona chahiye
    material_gaps = stage_material_gap(order, stage.work_stage_id)
    if material_gaps:
        return False, f"{stage.stage_name} cannot start yet: its material is not fully issued ({gap_text(material_gaps)}). Issue the rest from the Material issue page."
    blocker = lab_qc_blocker(order, stage)
    if blocker is not None:
        return False, f"{stage.stage_name} cannot start yet: {blocker.stage_name} needs a passed lab test with the test certificate (TC) uploaded first."
    # G27: stage ki machine kharab / maintenance me ho to start nahi hone dete. Sab ki sab kharab ho to doosri Active machine chunni padti hai
    # (form ka "Use this machine instead"); kuch hi kharab ho to unhe hata ke baaki Active se chalta hai.
    problem = stage_machine_problem(stage)
    swap_machine = None
    plan_ids = {row.machine_id for row in stage.machines}
    if target_machine_id:
        # Dashboard: manager ne khud machine chuni. Wo pehle se plan me hai to kuch badalna nahi (neeche wahi purani jaanch chalti hai).
        if target_machine_id not in plan_ids:
            swap_machine = db.session.get(Machines, target_machine_id)
            error = target_error(order, stage, swap_machine)
            if error:
                return False, f"{stage.stage_name} cannot start: {error}"
    elif problem is not None and problem["all_down"]:
        swap_id = form.get("swap_machine_id", type=int)
        if not any(option["id"] == swap_id for option in problem["swaps"]):
            if problem["swaps"]:
                return False, f"{stage.stage_name} cannot start: {problem['names']}. Choose another machine in the Start form (Use this machine instead)."
            return False, f"{stage.stage_name} cannot start: {problem['names']}. No other free machine is available for this stage, so wait until it is free."
        swap_machine = db.session.get(Machines, swap_id)
    machine_note = assigned_note
    if swap_machine is not None:
        # Machine pehle badal do: clash / waste / casting ke saare checks (aur stage ke ghante) chuni hui machine ke hisaab se chahiye (D1, D5).
        # Aage koi check fail ho to caller rollback karta hai, to ye badlav bhi wapas.
        old_names = problem["names"] if problem is not None else ", ".join(row.machine_name for row in stage.machines)
        assign_reason = (form.get("assign_reason") or "").strip()[:150]
        assign_machine(stage, swap_machine, kind=kind, reason=assign_reason)
        machine_note = f"Machine changed at start: {old_names} -> {swap_machine.name}" + (f", reason: {assign_reason}" if assign_reason else "")
        problem = None
    operator = (form.get("operator") or "").strip()[:60]
    if not operator:
        return False, "Enter the operator's name."
    # Timing clash lock: agle stage ki machine par doosre order ka garam maal aane wala ho aur ye kaam us gap me poora na ho to roko.
    # Wajah (kam se kam 3 akshar) likh kar "start anyway" ho sakta hai; wajah stage ke notes me jaati hai.
    clash = stage_clash(order, stage, in_production_orders())
    clash_reason = (form.get("clash_reason") or "").strip()[:150]
    if clash is not None and len(clash_reason) < 3:
        return False, f"{stage.stage_name} cannot start now. " + clash["message"]
    # C12: garam maal limit se zyada ruka ho to Start tabhi hoga jab wajah (kam se kam 3 akshar) likhi ho; wajah stage notes me jaati hai
    wait = metal_wait(order, stage)
    rewait_reason = (form.get("rewait_reason") or "").strip()[:100]
    if wait is not None and wait["over"] and len(rewait_reason) < 3:
        return False, (f"{stage.stage_name} cannot start yet: the metal from {wait['prev_name']} has waited {round(wait['minutes'])} min (limit {wait['limit']} min). "
                       f"Write what was done (for example re-heated) in the Start form.")
    # C8a: furnace (batch machine) poori nahi bhar rahi to Start tabhi hoga jab wajah (kam se kam 3 akshar) likhi ho; wajah stage notes me jaati hai
    is_melt = side_stage_info(order, stage) is None and bool(stage.work_stage and stage.work_stage.is_batch)
    waste = waste_payload(melt_plan(order, stage, melt_kg(stage))) if side_stage_info(order, stage) is None else None
    # C9 phase 2: combined melt me baaki members bhi start ke layak hon (warna poora melt rukta hai)
    members = melt_members(stage) if is_melt else [stage]
    for member in members:
        if member.id == stage.id:
            continue
        member_problem = _member_start_problem(member)
        if member_problem:
            return False, f"The combined melt cannot start: {member.production_order.prod_no} {member_problem} Fix it, or remove it from the melt."
    waste_reason = (form.get("waste_reason") or "").strip()[:100]
    if waste is not None and len(waste_reason) < 3:
        return False, (f"{stage.stage_name} cannot start yet: the furnace holds {waste['cap']:g} KG per melt but this melt fills {waste['melts'] * waste['cap'] - waste['unused']:g} KG "
                       f"({waste['unused']:g} KG unused). Write the reason in the Start form (for example no other order of the same alloy is ready).")
    started_at, error = _read_when("started_at", form)
    if error:
        return False, error
    # G14-4: melt taiyar hone par Casting machine free nahi hogi (aur garam maal limit se zyada rukega) to wajah likhni padti hai; wajah stage notes me
    cast = casting_ahead(order, stage, started_at) if is_melt else None
    cast_reason = (form.get("cast_reason") or "").strip()[:100]
    if cast is not None and cast["needs_reason"] and len(cast_reason) < 3:
        return False, f"{stage.stage_name} cannot start yet. {cast['message']} Write why you start now (for example the casting machine will be freed early) in the Start form."
    if previous and previous[-1].completed_at and started_at < previous[-1].completed_at:
        return False, f"{stage.stage_name} cannot start before {previous[-1].stage_name} finished ({previous[-1].completed_at.strftime('%d %b %H:%M')})."
    if problem is not None:
        # Kharab machine ki plan-row hata dete hain (warna dashboard par us machine par order chalta dikhta). Wajah stage notes me jaati hai.
        drop_rows(stage, [row for row, _machine in problem["rows"]], "left_out", problem["names"])
        settle(stage)
        machine_note = f"Not available, left out: {problem['names']}"
    stage.status = "In progress"
    stage.started_at = started_at
    stage.operator = operator
    side = side_stage_info(order, stage)
    stage.qty_in = side["qty"] if side else main_input(order, stage)       # flux stage: flux ki apni qty; baaki: metal chain
    notes = (form.get("notes") or "").strip()
    if clash is not None:
        notes = (notes + " | " if notes else "") + f"Timing clash overridden ({clash['machine_name']} due for {clash['other_order']}): {clash_reason}"
    if waste is not None:
        notes = (notes + " | " if notes else "") + f"Furnace not full ({waste['unused']:g} KG unused): {waste_reason}"
    if wait is not None and wait["over"]:
        notes = (notes + " | " if notes else "") + f"Metal waited {round(wait['minutes'])} min (limit {wait['limit']}): {rewait_reason}"
    if cast is not None and cast["needs_reason"]:
        notes = (notes + " | " if notes else "") + f"Casting machine busy at melt end ({cast['next_name']}, wait {'?' if cast['delay_minutes'] is None else round(cast['delay_minutes'])} min): {cast_reason}"
    if machine_note:
        notes = (notes + " | " if notes else "") + machine_note
    # C9 phase 2: har melt ko heat number; combined melt ke baaki members saath hi start (wahi operator / time, apna apna qty_in)
    heat_text = ""
    if is_melt:
        group = ensure_melt_group(stage)
        heat_text = f" Heat number {group.heat_no}."
        notes = (notes + " | " if notes else "") + f"Heat {group.heat_no}"
        for member in members:
            if member.id == stage.id:
                continue
            member.status = "In progress"
            member.started_at = started_at
            member.operator = operator
            member.qty_in = main_input(member.production_order, member)
            _add_note(member, f"Heat {group.heat_no}, melted together with {order.prod_no}")
        if len(members) > 1:
            heat_text += " Started together with " + ", ".join(m.production_order.prod_no for m in members if m.id != stage.id) + "."
    stage.notes = notes[:255] or None
    return True, f"{stage.stage_name} started for {order.prod_no}." + (f" {machine_note}." if machine_note else "") + heat_text


@routing_bp.route("/routing/start/<int:stage_id>", methods=["POST"])
def routing_start(stage_id):
    # Routing page ka Start: sara kaam start_stage() karta hai (Dashboard bhi wahi use karta hai); yahan sirf commit / rollback aur message
    stage, order, error = _stage_for_action(stage_id)
    if error:
        flash(error, "error")
        return _back()
    ok, message = start_stage(stage, order, request.form, kind="swap")
    if not ok:
        db.session.rollback()
        flash(message, "error")
        return _back()
    db.session.commit()
    flash(message, "success")
    return _back()


def _running_members(stage):
    # Hold / resume / cancel ek saath poore melt par lagte hain: is stage ke melt ke sab members (apna bhi)
    if stage.work_stage and stage.work_stage.is_batch and stage.melt_group_id:
        return melt_members(stage)
    return [stage]


@routing_bp.route("/routing/combine/<int:stage_id>", methods=["POST"])
def routing_combine(stage_id):
    # C9 phase 2: is Pending Melting stage ke melt me doosre order ka Melting stage jodo (same alloy, furnace me jagah ho, melt shuru hone se pehle)
    stage, order, error = _stage_for_action(stage_id)
    if error:
        flash(error, "error")
        return _back()
    other = db.session.get(ProductionOrderStage, request.form.get("other_stage_id", type=int) or 0)
    if other is None:
        flash("Choose the order to add to this melt.", "error")
        return _back()
    problem = combine_error(stage, other)
    if problem:
        flash(problem, "error")
        return _back()
    group = ensure_melt_group(stage)
    other.melt_group_id = group.id
    db.session.commit()
    flash(f"{other.production_order.prod_no} will be melted together with {order.prod_no} (heat number {group.heat_no}).", "success")
    return _back()


@routing_bp.route("/routing/uncombine/<int:stage_id>", methods=["POST"])
def routing_uncombine(stage_id):
    # Melt shuru hone se pehle kisi order ko melt se hatao.
    stage = db.session.get(ProductionOrderStage, stage_id)
    if stage is None or stage.melt_group_id is None:
        flash("This order is not part of a combined melt.", "error")
        return _back()
    members = melt_members(stage)
    if any(m.status != "Pending" for m in members):
        flash("The melt has already started, so orders cannot be removed.", "error")
        return _back()
    # Melt (heat number) delete nahi karte: akela member bacha to wo apne heat number ke saath akela melt ban jaata hai (number kabhi dobara nahi banta)
    stage.melt_group_id = None
    db.session.commit()
    flash(f"{stage.production_order.prod_no} was removed from the melt.", "success")
    return _back()


def _add_note(stage, text):
    # Stage ke notes me ek line jodta hai (255 akshar ki hadd ke andar; purani baat kate to kate, nayi hamesha rahe)
    old = stage.notes or ""
    stage.notes = ((old + " | " if old else "") + text)[-255:]


@routing_bp.route("/routing/hold/<int:stage_id>", methods=["POST"])
def routing_hold(stage_id):
    # Lights gayi / machine kharab / QC me ruka: timer ruk jaata hai (client meeting 2, #11). Wajah zaroori.
    stage, order, error = _stage_for_action(stage_id)
    if error:
        flash(error, "error")
        return _back()
    if stage.status != "In progress":
        flash(f"{stage.stage_name} is not running, so it cannot be put on hold.", "error")
        return _back()
    reason = (request.form.get("reason") or "").strip()[:120]
    if len(reason) < 3:
        flash("Write the reason for the hold (for example power cut, machine breakdown).", "error")
        return _back()
    held_at, error = _read_when("held_at")
    if error:
        flash(error, "error")
        return _back()
    if held_at < stage.started_at:
        flash("The hold time cannot be before the start time.", "error")
        return _back()
    members = [m for m in _running_members(stage) if m.status == "In progress"]
    for member in members:
        if member.started_at and held_at < member.started_at:
            continue
        member.status = "On hold"
        member.held_at = held_at
        member.hold_reason = reason
    db.session.commit()
    flash(f"{stage.stage_name} of {order.prod_no} is on hold. The timer has stopped." + (" The other orders of this melt are on hold too." if len(members) > 1 else ""), "success")
    return _back()


@routing_bp.route("/routing/resume/<int:stage_id>", methods=["POST"])
def routing_resume(stage_id):
    # Hold khatam: ruka hua time jod diya jaata hai, timer wahin se aage chalta hai
    stage, order, error = _stage_for_action(stage_id)
    if error:
        flash(error, "error")
        return _back()
    if stage.status != "On hold" or stage.held_at is None:
        flash(f"{stage.stage_name} is not on hold.", "error")
        return _back()
    resumed_at, error = _read_when("resumed_at")
    if error:
        flash(error, "error")
        return _back()
    if resumed_at < stage.held_at:
        flash("The resume time cannot be before the hold time.", "error")
        return _back()
    members = [m for m in _running_members(stage) if m.status == "On hold" and m.held_at is not None and resumed_at >= m.held_at]
    for member in members:
        minutes = (resumed_at - member.held_at).total_seconds() / 60
        member.hold_minutes = round((member.hold_minutes or 0) + minutes, 2)
        _add_note(member, f"Held {int(round(minutes))} min ({member.hold_reason})")
        member.status = "In progress"
        member.held_at = None
        member.hold_reason = None
    db.session.commit()
    flash(f"{stage.stage_name} of {order.prod_no} resumed." + (" The other orders of this melt resumed too." if len(members) > 1 else ""), "success")
    return _back()


@routing_bp.route("/routing/cancel_start/<int:stage_id>", methods=["POST"])
def routing_cancel_start(stage_id):
    # Galti se / kaam shuru hi nahi hua: stage wapas "Pending" (timer saaf). Issue hua material order par hi rehta hai. Wajah zaroori.
    stage, order, error = _stage_for_action(stage_id)
    if error:
        flash(error, "error")
        return _back()
    if stage.status not in ("In progress", "On hold"):
        flash(f"{stage.stage_name} is not running, so there is nothing to cancel.", "error")
        return _back()
    reason = (request.form.get("reason") or "").strip()[:120]
    if len(reason) < 3:
        flash("Write the reason for cancelling the run.", "error")
        return _back()
    members = [m for m in _running_members(stage) if m.status in ("In progress", "On hold")]
    if any(m.lab_qcs for m in members):
        flash(f"{stage.stage_name} has a lab test recorded, so the run cannot be cancelled. Put it on hold, or finish it.", "error")
        return _back()
    for member in members:
        _add_note(member, f"Run cancelled ({reason}) - was started {member.started_at.strftime('%d %b %H:%M')}")
        member.status = "Pending"
        member.started_at = None
        member.qty_in = None
        member.held_at = None
        member.hold_reason = None
        member.hold_minutes = 0
        # Start par machine badli thi (Dashboard Assign / Use this machine instead) to plan wali machine wapas: nahi to order us machine par
        # atka rehta jahan kaam hua hi nahi
        if restore_planned(member):
            _add_note(member, "Planned machine restored")
    db.session.commit()
    flash(f"{stage.stage_name} of {order.prod_no} is back to waiting to start. Start it again when the machine really starts."
          + (" The other orders of this melt went back too." if len(members) > 1 else ""), "success")
    return _back()


@routing_bp.route("/routing/complete/<int:stage_id>", methods=["POST"])
def routing_complete(stage_id):
    stage, order, error = _stage_for_action(stage_id)
    if error:
        flash(error, "error")
        return _back()
    if stage.status == "On hold":
        flash(f"{stage.stage_name} is on hold. Resume it before completing.", "error")
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
    # C15: Spooling ke baad ke stages me scrap PCS me likha jaata hai; DB me KG chahiye (asli KG per piece se). Message PCS me dikhte hain.
    pm = None if side else pcs_mode(order, stage)
    pcs_all = pm is not None and pm["kind"] == "all"
    if pcs_all and scrap > 0:
        scrap = round(scrap * pm["wa"], 4)
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
        if pcs_all:
            flash(f"Scrap ({scrap / pm['wa']:g} PCS) cannot be more than what came into this stage ({qty_in / pm['wa']:g} PCS).", "error")
        else:
            flash(f"Scrap ({scrap:g}) cannot be more than what came into this stage ({qty_in:g} {unit}).", "error")
        return _back()
    qty_out = max(qty_in - scrap, 0.0)
    if qty_out <= EPS:
        flash("Scrap cannot be the whole quantity. Some material must go on to the next stage.", "error")
        return _back()
    # C13: ek spool / box me uski capacity (kg_per_pack) se zyada wire nahi aa sakta. Average = good wire / bane hue packs; usse zyada ho to ginti galat hai.
    for line in stage_lines(order, stage):
        used = used_map.get(line.id)
        if used and used > 0 and line.is_packing and line.kg_per_pack:
            avg = qty_out / used
            if avg > line.kg_per_pack * (1 + 1e-6) + EPS:
                pack_name = line.raw_material.name if line.raw_material else "Pack"
                pack_unit = line.raw_material.base_unit.code if line.raw_material and line.raw_material.base_unit else ""
                flash(f"{pack_name}: {qty_out:g} KG in {used:g} {pack_unit} is {avg:.3f} KG each, but one holds at most {line.kg_per_pack:g} KG. Count again, or use more {pack_unit}.", "error")
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
        _add_note(stage, note)          # hold / clash wali purani lines mitti nahi, nayi note unke saath judti hai
    db.session.commit()
    summary = order_summary(order, today_ist())
    # Machine ab khali hui: uski queue ka agla order dikhane ke liye "after" me khatam hua stage bhejte hain (routing page par box banta hai)
    if summary["all_done"]:
        flash(f"{stage.stage_name} done. All stages of {order.prod_no} are complete.", "success")
        return redirect(url_for("routing.routing_list", tab="done", after=stage.id))
    flash(f"{stage.stage_name} done for {order.prod_no}. Next: {summary['current'].stage_name}.", "success")
    return redirect(url_for("routing.routing_list", tab="running", after=stage.id))


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
    # fix_list #4: Done stage (Melting) ke lab test me extra metal dala to wo us stage ke input / output me aur agle stage ke input me judna chahiye.
    # Agla metal stage pehle hi chal / ho chuka ho to uska input badal nahi sakte — tab correction yahan band (pehle usse pehle ka kaam khol ke karo).
    side_here = side_stage_info(order, stage)
    kg_extra = round(sum(q for lid, q in wanted_extra.items() if counts_to_input(allowed_lines[lid], side_here)), 4) if side_here is None else 0.0
    if wanted_extra and stage.status == "Done" and kg_extra > 0:
        later = next_main_stage(order, stage)
        if later is not None and later.status != "Pending":
            flash(f"{later.stage_name} has already started, so extra metal cannot be added to {stage.stage_name} now. Add the correction before {later.stage_name} starts.", "error")
            return _back()
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
            # C19: stage pehle hi Complete ho chuka ho (used likha ja chuka) to correction ka maal seedha melt me gaya hai — use me jod do.
            # Warna wo "unaccounted" dikhta aur operator ko jhootha return / write-off karna padta. Stage chalu ho to Complete form ka default
            # (_auto_extra_qty) ye khud sambhal leta hai, isliye wahan kuch nahi karna.
            was_used = line.used_qty
            if stage.status == "Done" and line.used_qty is not None:
                line.used_qty = round(line.used_qty + extra_qty, 4)
                # Metal ka input badha to output bhi (Melting ka scrap baad me likha jaata hai, isliye abhi 0) — agla stage inhi se input leta hai
                if side_here is None and counts_to_input(line, side_here):
                    stage.qty_in = round((stage.qty_in or 0) + extra_qty, 4)
                    stage.qty_out = round((stage.qty_out or 0) + extra_qty, 4)
            rm = line.raw_material
            # "in_input": ye correction agle stage ke input me judta hai ya nahi (flux / side stage / used likha hi nahi — to nahi); correction_in() sirf yahi dikhata hai
            joins_input = side_here is None and counts_to_input(line, side_here) and not (stage.status == "Done" and was_used is None)
            corrections.append({"material": rm.name if rm else "", "qty": extra_qty, "unit": rm.base_unit.code if rm and rm.base_unit else "",
                                "added_by": added_by, "reason": extra_reason, "issue_no": issue.issue_no, "in_input": bool(joins_input)})
    row = StageLabQC(stage_id=stage.id, tested_at=tested_at, tested_by=tested_by, result=result, remarks=remarks, corrections=corrections or None)
    db.session.add(row)
    db.session.flush()                      # id chahiye: file ka folder QC id se banta hai
    if has_file:
        folder = os.path.join(current_app.config["UPLOAD_FOLDER"], "lab_qc", str(row.id))
        os.makedirs(folder, exist_ok=True)
        name = secure_filename(tc.filename) or ("tc." + ext)
        tc.save(os.path.join(folder, name))
        row.tc_file = "lab_qc/" + str(row.id) + "/" + name         # DB me hamesha "/"
    # C9 phase 2: ek melt ka ek hi lab test — wahi result + wahi TC file melt ke baaki orders ke stage par bhi (corrections sirf is order par, double issue nahi)
    mirrored = []
    if stage.melt_group_id:
        for member in melt_members(stage):
            if member.id == stage.id or member.status == "Pending":
                continue
            copy = StageLabQC(stage_id=member.id, tested_at=tested_at, tested_by=tested_by, result=result, tc_file=row.tc_file,
                              remarks=((remarks + " | ") if remarks else "") + f"Heat {stage.melt_group.heat_no}, tested with {order.prod_no}"[:255])
            db.session.add(copy)
            mirrored.append(member.production_order.prod_no)
    db.session.commit()
    if mirrored:
        flash(f"The same lab result and TC were also saved for {', '.join(mirrored)} (same melt).", "success")
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


@routing_bp.route("/routing/tc/<int:qc_id>/print")
def routing_tc_print(qc_id):
    """TC ka branded A4 print (client meeting 2, #15): Nrupex letterhead, order / product / lab result, lab ki uploaded TC (image ya PDF) neeche,
    aur poore page par Nrupex logo + naam ka halka watermark. Party ka naam ?party= se (print ke waqt likhte hain, kahin save nahi hota)."""
    row = db.session.get(StageLabQC, qc_id)
    if row is None or not row.tc_file:
        abort(404)
    stage = row.stage
    order = stage.production_order
    ext = row.tc_file.rsplit(".", 1)[-1].lower() if "." in row.tc_file else ""
    party = (request.args.get("party") or "").strip()[:80]
    members = melt_members(stage) if stage.melt_group_id else []
    return render_template("tc_print.html", qc=row, stage=stage, order=order, party=party, is_pdf=(ext == "pdf"), batch_kg=order_batch_kg(order),
                           heat_no=stage.melt_group.heat_no if stage.melt_group_id else None,
                           melt_orders=[{"prod_no": m.production_order.prod_no, "kg": stage_kg(m)} for m in members] if len(members) > 1 else [])


@routing_bp.route("/routing/scrap_photo/<int:stage_id>")
def routing_scrap_photo(stage_id):
    # Billet (lattha) stage ke scrap ka proof photo kholna
    stage = db.session.get(ProductionOrderStage, stage_id)
    if stage is None or not stage.scrap_photo:
        abort(404)
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], stage.scrap_photo)
