# Live machine dashboard (client meeting 2, change 10): har production line aur uski har machine ka abhi ka haal.
# Sirf padhta hai, kuch save nahi karta. Data: Machines (line), ProductionOrderStage (In progress = machine chal rahi hai),
# aur live_schedule (agla kaun si machine par aane wala hai).
from flask import Blueprint, render_template

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


@dashboard_bp.route("/dashboard")
def dashboard_page():
    return render_template("dashboard.html", active_nav="dashboard", board=machine_board())
