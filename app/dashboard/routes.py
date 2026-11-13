# Live machine dashboard (client meeting 2, change 10): har production line aur uski har machine ka abhi ka haal.
# Sirf padhta hai, kuch save nahi karta. Data: Machines (line), ProductionOrderStage (In progress = machine chal rahi hai),
# aur live_schedule (agla kaun si machine par aane wala hai).
from flask import Blueprint, jsonify, render_template

from app.models import Machines, ProductionLine, ProductionOrder, ProductionOrderStage
from app.production_orders.scheduler import live_schedule, now_ist, today_ist

dashboard_bp = Blueprint("dashboard", __name__, template_folder="templates")

QUEUE_STATUSES = ("Released", "In production")      # Draft order abhi plan me pakka nahi, isliye queue me nahi ginte


def hours_text(minutes):
    # 135 -> "2 h 15 m", 40 -> "40 m"
    minutes = max(int(minutes), 0)
    hours, mins = divmod(minutes, 60)
    return f"{hours} h {mins:02d} m" if hours else f"{mins} m"


def running_by_machine(now):
    """{machine_id: [info]} — jis stage ka status "In progress" hai, uski saari chuni hui machines chal rahi maani jaati hain
    (asli machine routing me Complete par tick hoti hai). Elapsed time stage ke asli Start se ginte hain, order assign hone se nahi."""
    out = {}
    stages = (ProductionOrderStage.query.join(ProductionOrder, ProductionOrder.id == ProductionOrderStage.production_order_id)
              .filter(ProductionOrderStage.status == "In progress", ProductionOrder.is_deleted == False).all())
    for stage in stages:
        order = stage.production_order
        elapsed = int((now - stage.started_at).total_seconds() // 60) if stage.started_at else 0
        planned_min = int(round((stage.planned_hours or 0) * 60)) if stage.planned_hours else None
        info = {"order_id": order.id, "prod_no": order.prod_no, "product": order.product.name if order.product else "",
                "stage": stage.stage_name, "operator": stage.operator or "", "kg": round(stage.qty_in or 0, 2),
                "elapsed_min": elapsed, "elapsed_text": hours_text(elapsed), "planned_text": hours_text(planned_min) if planned_min else "",
                "over_min": (elapsed - planned_min) if planned_min and elapsed > planned_min else 0,
                "started": stage.started_at.strftime("%d %b %H:%M") if stage.started_at else ""}
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
                out.setdefault(row.machine_id, []).append({"order_id": order.id, "prod_no": order.prod_no,
                                                           "product": order.product.name if order.product else "",
                                                           "stage": stage.stage_name, "start": start})
    for rows in out.values():
        rows.sort(key=lambda r: (r["start"], r["prod_no"]))
    return out


def machine_board(today=None, now=None):
    """Wapas {"lines": [{"name", "code", "capacity", "handler", "machines": [tile], "running", "free", "inactive"}], "total": {...}}.
    Tile state: "running" (stage chal raha), "free", "inactive" (Machine master me band). Bina line ki machines last me "No line"."""
    today = today or today_ist()
    now = now or now_ist()
    running = running_by_machine(now)
    queue = queue_by_machine(today)
    machines = Machines.query.filter_by(is_deleted=False).order_by(Machines.code).all()

    def tile(machine):
        runs = running.get(machine.id, [])
        waiting = queue.get(machine.id, [])
        state = "running" if runs else ("free" if machine.status == "active" else "inactive")
        return {"id": machine.id, "code": machine.code, "name": machine.name, "stage_name": machine.work_stage.name if machine.work_stage else "",
                "capacity": machine.capacity_text, "state": state, "runs": runs, "next": waiting[0] if waiting else None,
                "queue_count": len(waiting), "master_inactive": machine.status != "active"}

    groups = []
    for line in ProductionLine.query.filter_by(is_deleted=False).order_by(ProductionLine.code).all():
        groups.append({"name": line.name, "code": line.code, "capacity": line.daily_capacity_kg, "handler": line.handler or "",
                       "line_active": line.is_active, "machines": [tile(m) for m in machines if m.line_id == line.id]})
    loose = [tile(m) for m in machines if m.line_id is None]
    if loose:
        groups.append({"name": "Machines without a line", "code": "", "capacity": None, "handler": "", "line_active": True, "machines": loose})
    for group in groups:
        group["running"] = len([t for t in group["machines"] if t["state"] == "running"])
        group["free"] = len([t for t in group["machines"] if t["state"] == "free"])
        group["inactive"] = len([t for t in group["machines"] if t["state"] == "inactive"])
    total = {key: sum(g[key] for g in groups) for key in ("running", "free", "inactive")}
    total["machines"] = total["running"] + total["free"] + total["inactive"]
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
        if stage.status == "In progress" and stage.started_at:
            actual = round((now - stage.started_at).total_seconds() / 3600, 2)
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
            "running_stage": running_stage.stage_name}


@dashboard_bp.route("/dashboard/machine/<int:machine_id>")
def machine_detail(machine_id):
    """Tile par click: us machine ka pop-up data (JSON). Chal rahe order(s) ka poora planning + is machine ki aage ki queue."""
    machine = Machines.query.filter_by(id=machine_id, is_deleted=False).first_or_404()
    orders = []
    stages = (ProductionOrderStage.query.join(ProductionOrder, ProductionOrder.id == ProductionOrderStage.production_order_id)
              .filter(ProductionOrderStage.status == "In progress", ProductionOrder.is_deleted == False).all())
    for stage in stages:
        if any(row.machine_id == machine.id for row in stage.machines):
            orders.append(order_detail(stage.production_order, stage))
    queue = [{"prod_no": q["prod_no"], "product": q["product"], "stage": q["stage"], "start": day_text(q["start"])}
             for q in queue_by_machine(today_ist()).get(machine.id, [])]
    return jsonify({"machine": {"name": machine.name, "code": machine.code, "stage": machine.work_stage.name if machine.work_stage else "",
                                "line": machine.line.name if machine.line else "No line", "capacity": machine.capacity_text,
                                "status": machine.status},
                    "orders": orders, "queue": queue})


@dashboard_bp.route("/dashboard")
def dashboard_page():
    return render_template("dashboard.html", active_nav="dashboard", board=machine_board())
