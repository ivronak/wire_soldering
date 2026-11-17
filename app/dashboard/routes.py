# Live machine dashboard (client meeting 2, change 10): har production line aur uski har machine ka abhi ka haal.
# Dekhne ke saath ek hi cheez badalta hai: machine ki queue me order ko upar / neeche karna (client meeting 2, #11). Data: Machines (line), ProductionOrderStage (In progress = machine chal rahi hai),
# aur live_schedule (agla kaun si machine par aane wala hai).
from flask import Blueprint, jsonify, render_template

from app.extensions import db

from app.models import Machines, ProductionLine, ProductionOrder, ProductionOrderStage, ProductionOrderStageMachine, WorkStage
from app.production_orders.scheduler import live_schedule, now_ist, persist_schedule, queue_orders, today_ist
from app.routing.handoff import hot_handoffs, hours_text as handoff_text

dashboard_bp = Blueprint("dashboard", __name__, template_folder="templates")

QUEUE_STATUSES = ("Released", "In production")      # Draft order abhi plan me pakka nahi, isliye queue me nahi ginte


def hours_text(minutes):
    # 135 -> "2 h 15 m", 40 -> "40 m"
    minutes = max(int(minutes), 0)
    hours, mins = divmod(minutes, 60)
    return f"{hours} h {mins:02d} m" if hours else f"{mins} m"


def clock_text(seconds):
    # Chalne ka time hh:mm:ss (24 ghante se zyada ho to ghante badhte rehte hain: 126:05:09)
    seconds = max(int(seconds), 0)
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def running_by_machine(now):
    """{machine_id: [info]} — jis stage ka status "In progress" (ya "On hold") hai, uski saari chuni hui machines us order se bandhi maani jaati hain
    (asli machine routing me Complete par tick hoti hai). Elapsed time stage ke asli Start se ginte hain, order assign hone se nahi;
    hold me ruka hua time hat jaata hai aur hold chal raha ho to timer wahin ruka dikhta hai (held=True)."""
    out = {}
    stages = (ProductionOrderStage.query.join(ProductionOrder, ProductionOrder.id == ProductionOrderStage.production_order_id)
              .filter(ProductionOrderStage.status.in_(["In progress", "On hold"]), ProductionOrder.is_deleted == False).all())
    for stage in stages:
        order = stage.production_order
        elapsed_sec = stage.worked_seconds(now)
        elapsed = elapsed_sec // 60
        planned_min = int(round((stage.planned_hours or 0) * 60)) if stage.planned_hours else None
        stages_of_order = list(order.stages)
        position = next((i for i, st in enumerate(stages_of_order) if st.id == stage.id), len(stages_of_order) - 1)
        next_stage = stages_of_order[position + 1].stage_name if position + 1 < len(stages_of_order) else "Production output"
        info = {"order_id": order.id, "next_stage": next_stage, "prod_no": order.prod_no, "product": order.product.name if order.product else "",
                "stage": stage.stage_name, "operator": stage.operator or "", "kg": round(stage.qty_in or 0, 2),
                "elapsed_min": elapsed, "elapsed_text": hours_text(elapsed), "elapsed_sec": elapsed_sec, "elapsed_clock": clock_text(elapsed_sec), "planned_text": hours_text(planned_min) if planned_min else "",
                "over_min": (elapsed - planned_min) if planned_min and elapsed > planned_min else 0,
                "pct": min(100, int(round(100 * elapsed / planned_min))) if planned_min else 0,
                "started": stage.started_at.strftime("%d %b %H:%M") if stage.started_at else "",
                "held": stage.status == "On hold", "hold_reason": stage.hold_reason or "",
                "held_at": stage.held_at.strftime("%d %b %H:%M") if stage.held_at else ""}
        info["over_text"] = hours_text(info["over_min"]) if info["over_min"] else ""
        for row in stage.machines:
            out.setdefault(row.machine_id, []).append(info)
    return out


def queue_by_machine(today):
    """{machine_id: [info]} — Released / In production orders ke Pending stages jo is machine par chalenge, jaldi wale pehle.
    Dates live_schedule se (queue ke hisaab se), isliye reorder karne par yahan bhi badal jaati hain."""
    ordered, _materials, schedule = live_schedule(today)
    out = {}
    for order in ordered:
        info = schedule.get(order.id)
        if info is None or order.status not in QUEUE_STATUSES:
            continue
        for index, stage in enumerate(order.stages):
            if stage.status != "Pending" or index >= len(info["windows"]):
                continue
            start = info["windows"][index][0]
            for row in stage.machines:
                out.setdefault(row.machine_id, []).append({"order_id": order.id, "stage_id": stage.id, "prod_no": order.prod_no,
                                                           "product": order.product.name if order.product else "",
                                                           "stage": stage.stage_name, "start": start, "status": order.status,
                                                           "position": order.queue_position, "batch_kg": round((order.planned_qty or 0) * (order.unit_weight or 1), 2)})
    for rows in out.values():
        rows.sort(key=lambda r: (r["position"] if r["position"] is not None else 10 ** 9, r["prod_no"]))      # queue ka number hi turn tay karta hai (dates usi se bani hain)
    return out


def incoming_by_machine(now):
    """{machine_id: [info]} — jis machine par kisi order ka garam maal (Melting ka output) kuch hi der me aane wala hai, jaldi wala pehle."""
    orders = ProductionOrder.query.filter(ProductionOrder.is_deleted == False, ProductionOrder.status == "In production").all()
    out = {}
    for h in hot_handoffs(orders, now):
        out.setdefault(h["machine_id"], []).append({"prod_no": h["order"].prod_no, "stage": h["stage"].stage_name, "prev_stage": h["prev_stage"].stage_name,
                                                    "minutes_left": h["minutes_left"],
                                                    "text": "now" if h["minutes_left"] <= 0.5 else "in " + handoff_text(h["minutes_left"])})
    for rows in out.values():
        rows.sort(key=lambda r: r["minutes_left"])
    return out


def machine_board(today=None, now=None):
    """Wapas {"lines": [{"name", "code", "capacity", "handler", "machines": [tile], "running", "free", "inactive"}], "total": {...}}.
    Tile state: "running" (stage chal raha), "free", "inactive" (Machine master me band). Bina line ki machines last me "No line"."""
    today = today or today_ist()
    now = now or now_ist()
    running = running_by_machine(now)
    queue = queue_by_machine(today)
    incoming = incoming_by_machine(now)
    # Stage ka order Work Stage master ke "Order" number se (chhota = pehle: Flux, Melting, Casting ...). Machines usi order me dikhti hain.
    stage_rank = {}
    for index, ws in enumerate(WorkStage.query.filter_by(is_deleted=False).all()):
        stage_rank[ws.id] = (int(ws.sort_order or 0), ws.id)
    ranked = sorted(stage_rank, key=lambda i: stage_rank[i])
    stage_no = {stage_id: n + 1 for n, stage_id in enumerate(ranked)}          # 1, 2, 3 ... poore process me stage ka number
    machines = Machines.query.filter_by(is_deleted=False).order_by(Machines.code).all()
    machines.sort(key=lambda m: (stage_rank.get(m.work_stage_id, (10 ** 9, 0)), m.code))

    def tile(machine):
        runs = running.get(machine.id, [])
        waiting = queue.get(machine.id, [])
        state = "running" if runs else ("free" if machine.status == "active" else "inactive")
        held = bool(runs) and all(r["held"] for r in runs)          # sab hold par ho to card "On hold" dikhta hai
        return {"id": machine.id, "code": machine.code, "name": machine.name, "stage_name": machine.work_stage.name if machine.work_stage else "",
                "stage_id": machine.work_stage_id, "stage_no": stage_no.get(machine.work_stage_id, 0),
                "capacity": machine.capacity_text, "state": state, "runs": runs, "next": waiting[0] if waiting else None,
                "queue_count": len(waiting), "master_inactive": machine.status != "active", "held": held,
                # G27: kharab / maintenance / retired — tile par alag rang aur naam se dikhta hai (pehle sab "Inactive" tha)
                "mstatus": machine.status, "down_text": {"breakdown": "Breakdown", "maintenance": "Maintenance", "retired": "Retired"}.get(machine.status, ""),
                "down_phrase": {"breakdown": "under breakdown", "maintenance": "under maintenance", "retired": "retired"}.get(machine.status, ""),
                "incoming": (incoming.get(machine.id) or [None])[0]}

    groups = []
    for line in ProductionLine.query.filter_by(is_deleted=False).order_by(ProductionLine.code).all():
        groups.append({"name": line.name, "code": line.code, "capacity": line.daily_capacity_kg, "handler": line.handler or "",
                       "line_active": line.is_active, "machines": [tile(m) for m in machines if m.line_id == line.id]})
    loose = [tile(m) for m in machines if m.line_id is None]
    if loose:
        groups.append({"name": "Machines without a line", "code": "", "capacity": None, "handler": "", "line_active": True, "machines": loose})
    for group in groups:
        # Line ke andar stage-wise column: process ke order me (jis stage me us line ki machine ho wahi dikhta hai)
        stages = []
        for t in group["machines"]:
            if not stages or stages[-1]["id"] != t["stage_id"]:
                stages.append({"id": t["stage_id"], "no": t["stage_no"], "name": t["stage_name"], "machines": []})
            stages[-1]["machines"].append(t)
        for st in stages:
            st["running"] = len([t for t in st["machines"] if t["state"] == "running"])
            st["free"] = len([t for t in st["machines"] if t["state"] == "free"])
            st["held"] = len([t for t in st["machines"] if t["held"]])       # "running" me hi gine jaate hain, par dikhate alag (G24)
        group["stages"] = stages
        group["running"] = len([t for t in group["machines"] if t["state"] == "running"])
        group["free"] = len([t for t in group["machines"] if t["state"] == "free"])
        group["held"] = len([t for t in group["machines"] if t["held"]])
        group["inactive"] = len([t for t in group["machines"] if t["state"] == "inactive"])
    total = {key: sum(g[key] for g in groups) for key in ("running", "free", "inactive")}
    total["machines"] = total["running"] + total["free"] + total["inactive"]
    # G24: hold par ruki machine "running" state me hi rehti hai (machine busy hai), par KPI me alag dikhate hain taaki "Running" sach batae
    total["held"] = len([t for g in groups for t in g["machines"] if t["held"]])
    # G27: "Unavailable" = machine ka status Active nahi (breakdown / maintenance / retired) — chahe us par abhi koi run ho ya na ho
    total["down"] = len([t for g in groups for t in g["machines"] if t["mstatus"] != "active"])
    total["orders"] = len({r["order_id"] for rows in running.values() for r in rows})
    return {"groups": groups, "total": total, "now": now}


def day_text(day):
    return day.strftime("%d %b") if day else ""


def order_detail(order, running_stage):
    """Ek order ka pop-up wala haal: batch KG, line, dates, saare stages (status, machines, plan vs asli ghante) aur material (kitna lagna / kitna issue hua).
    running_stage = wo stage jo is machine par chal raha hai (pop-up me highlight hota hai)."""
    now = now_ist()
    stages = []
    for stage in order.stages:
        if stage.status in ("In progress", "On hold") and stage.started_at:
            actual = round(stage.worked_seconds(now) / 3600, 2)
        else:
            actual = stage.actual_hours
        stages.append({"name": stage.stage_name, "status": stage.status, "is_this": stage.id == running_stage.id,
                       "machines": [row.machine_name for row in stage.machines], "start": day_text(stage.start_date), "end": day_text(stage.end_date),
                       "planned_h": round(stage.planned_hours, 2) if stage.planned_hours else None, "actual_h": actual,
                       "operator": stage.operator or "", "qty_in": round(stage.qty_in, 2) if stage.qty_in is not None else None,
                       "qty_out": round(stage.qty_out, 2) if stage.qty_out is not None else None})
    materials = [{"name": line.raw_material.name if line.raw_material else "", "required": round(line.required_qty, 3), "issued": round(line.issued_qty, 3),
                  "unit": line.raw_material.base_unit.code if line.raw_material and line.raw_material.base_unit else ""} for line in order.lines]
    done = len([s for s in order.stages if s.status == "Done"])
    return {"order_id": order.id, "prod_no": order.prod_no, "product": order.product.name if order.product else "", "status": order.status,
            "line": order.line.name if order.line else "", "batch_kg": round((order.planned_qty or 0) * (order.unit_weight or 1), 2),
            "planned_start": day_text(order.planned_start_date), "planned_end": day_text(order.planned_end_date),
            "needed_by": day_text(order.needed_by_date), "done": done, "total": len(order.stages), "stages": stages, "materials": materials,
            "running_stage": running_stage.stage_name, "held": running_stage.status == "On hold",
            "hold_reason": running_stage.hold_reason or ""}


LEARN_RUNS = 5           # pichhle itne completed runs se machine ki asli speed nikalte hain
LEARN_MIN_RUNS = 3       # isse kam run ho to "abhi kaafi run nahi" (andaza galat ho sakta hai)


def learned_speed(machine):
    """Machine ki asli speed (KG / ghanta) pichhle completed runs se — sirf dikhane ke liye, planning abhi rated capacity se hi hoti hai.
    Run tab ginta hai jab wo stage sirf isi ek machine par chala ho (do machine ho to kaam ka hissa pata nahi), maal KG me aur ghante > 0 ho.
    Speed = kul KG / kul ghante (hold ka time pehle se hata hua). Wapas {"runs", "kg_per_hour", "rated", "ok"}."""
    stages = (ProductionOrderStage.query.join(ProductionOrderStageMachine, ProductionOrderStageMachine.stage_id == ProductionOrderStage.id)
              .join(ProductionOrder, ProductionOrder.id == ProductionOrderStage.production_order_id)
              .filter(ProductionOrderStageMachine.machine_id == machine.id, ProductionOrderStageMachine.used == True,
                      ProductionOrderStage.status == "Done", ProductionOrderStage.completed_at.isnot(None),
                      ProductionOrder.is_deleted == False)
              .order_by(ProductionOrderStage.completed_at.desc()).all())
    kg = hours = 0.0
    runs = 0
    for stage in stages:
        if sum(1 for row in stage.machines if row.used) != 1:
            continue
        worked = stage.actual_hours
        if not worked or worked <= 0 or not stage.qty_in or stage.qty_in <= 0:
            continue
        if _is_side_stage(stage):
            continue                  # flux jaisa side stage KG nahi hota
        kg += stage.qty_in
        hours += worked
        runs += 1
        if runs >= LEARN_RUNS:
            break
    speed = round(kg / hours, 1) if runs and hours > 0 else None
    return {"runs": runs, "kg_per_hour": speed, "rated": machine.capacity_per_hour, "ok": runs >= LEARN_MIN_RUNS and speed is not None}


def _is_side_stage(stage):
    from app.routing.routes import side_stage_info
    return side_stage_info(stage.production_order, stage) is not None


def learned_text(info):
    # Pop-up ki line: "Learned 34 KG/hr from last 5 runs (rated 40 KG/hr)" ya "Not enough runs yet (1 of 3)"
    if not info["ok"]:
        return f"Learned speed: not enough runs yet ({info['runs']} of {LEARN_MIN_RUNS} needed)"
    text = f"Learned speed: {info['kg_per_hour']:g} KG/hr from the last {info['runs']} run{'s' if info['runs'] != 1 else ''}"
    if info["rated"]:
        text += f" (rated {info['rated']:g} KG/hr)"
    return text


def machine_payload(machine):
    """Pop-up ka poora data (JSON ke liye dict): chal rahe order(s), garam maal aane wala, aur is machine ki queue (upar / neeche ke ishare ke saath)."""
    orders = []
    stages = (ProductionOrderStage.query.join(ProductionOrder, ProductionOrder.id == ProductionOrderStage.production_order_id)
              .filter(ProductionOrderStage.status.in_(["In progress", "On hold"]), ProductionOrder.is_deleted == False).all())
    for stage in stages:
        if any(row.machine_id == machine.id for row in stage.machines):
            orders.append(order_detail(stage.production_order, stage))
    rows = machine_queue(machine.id)
    queue = []
    for index, q in enumerate(rows):
        movable = q["status"] == "Released"            # "In production" order queue me aage jam hai, use nahi hilate
        queue.append({"order_id": q["order_id"], "prod_no": q["prod_no"], "product": q["product"], "stage": q["stage"], "start": day_text(q["start"]),
                      "status": q["status"], "batch_kg": q["batch_kg"], "position": q["position"],
                      "can_up": movable and index > 0 and rows[index - 1]["status"] == "Released",
                      "can_down": movable and index < len(rows) - 1})
    incoming = incoming_by_machine(now_ist()).get(machine.id, [])
    learned = learned_speed(machine)
    return {"incoming": incoming, "machine": {"id": machine.id, "name": machine.name, "code": machine.code, "stage": machine.work_stage.name if machine.work_stage else "",
                                "line": machine.line.name if machine.line else "No line", "capacity": machine.capacity_text,
                                "status": machine.status, "learned": learned_text(learned),
                                "learned_kg_per_hour": learned["kg_per_hour"] if learned["ok"] else None},
            "orders": orders, "queue": queue}


def machine_queue(machine_id):
    # Is machine par intezaar karte orders (ek order ek baar), jaldi wala pehle
    seen, rows = set(), []
    for q in queue_by_machine(today_ist()).get(machine_id, []):
        if q["order_id"] not in seen:
            seen.add(q["order_id"])
            rows.append(q)
    return rows


@dashboard_bp.route("/dashboard/machine/<int:machine_id>")
def machine_detail(machine_id):
    """Tile par click: us machine ka pop-up data (JSON). Chal rahe order(s) ka poora planning + is machine ki aage ki queue."""
    machine = Machines.query.filter_by(id=machine_id, is_deleted=False).first_or_404()
    return jsonify(machine_payload(machine))


@dashboard_bp.route("/dashboard/machine/<int:machine_id>/move/<int:order_id>/<direction>", methods=["POST"])
def machine_queue_move(machine_id, order_id, direction):
    """Machine ki queue me order ko ek jagah upar / neeche karo. Asal me us order aur padosi order ki jagah queue me badal jaati hai
    (queue ek hi hai, isliye Production order list me bhi wahi order dikhta hai) aur dates dobara bante hain. Wapas naya pop-up data."""
    machine = Machines.query.filter_by(id=machine_id, is_deleted=False).first_or_404()
    if direction not in ("up", "down"):
        return jsonify({"error": "Direction must be up or down."}), 400
    rows = machine_queue(machine.id)
    ids = [q["order_id"] for q in rows]
    if order_id not in ids:
        return jsonify({"error": "This order is not waiting for this machine."}), 400
    index = ids.index(order_id)
    other = index - 1 if direction == "up" else index + 1
    if other < 0 or other >= len(rows):
        return jsonify({"error": "It is already at the " + ("front" if direction == "up" else "end") + " of this machine's queue."}), 400
    if rows[index]["status"] != "Released" or rows[other]["status"] != "Released":
        return jsonify({"error": "Only released orders can be moved. An order already in production keeps its place."}), 400
    waiting = [o for o in queue_orders() if o.status in ("Draft", "Released")]
    by_id = {o.id: o for o in waiting}
    first, second = by_id[order_id], by_id[rows[other]["order_id"]]
    i, j = waiting.index(first), waiting.index(second)
    waiting[i], waiting[j] = waiting[j], waiting[i]
    frozen = [o for o in queue_orders() if o.status == "In production"]
    for position, item in enumerate(frozen + waiting, start=1):
        item.queue_position = position
    db.session.flush()
    persist_schedule()
    db.session.commit()
    return jsonify(machine_payload(machine))


@dashboard_bp.route("/dashboard")
def dashboard_page():
    return render_template("dashboard.html", active_nav="dashboard", board=machine_board())
