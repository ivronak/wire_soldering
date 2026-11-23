# Dashboard "Assign & Start" (client: machine ya aadmi ek minute bhi khali nahi baithna chahiye): ek free machine par kisi bhi line ke intezaar karte order ka
# stage chalana. Yahan sirf "kaun order mil sakta hai" aur "form ko kya poochna padega" nikalte hain; asli Start routing.routes.start_stage() hi karta hai
# (wahi saare gates: material issued, lab TC, pichhla stage Done, machine busy / kharab, garam maal, furnace bhari, casting) — koi gate bypass nahi.
# Ye file kuch commit nahi karti; route commit / rollback karta hai.
from app.extensions import db
from app.models import ProductionOrder
from app.production_orders.scheduler import today_ist
from app.routing.assign import assign_machine, target_error
from app.routing.busy import busy_machines

QUEUE_STATUSES = ("Released", "In production")


def _routing():
    # routing.routes yahin import (module load-order ke jhanjhat se bachne ke liye, dashboard ke baaki helpers ki tarah)
    from app.routing import routes as routing_routes
    return routing_routes


def start_blockers(order, stage):
    """Wajah (English text list) jinki wajah se is order ka ye stage abhi kisi bhi machine par start nahi ho sakta. [] = ready.
    Machine ki apni dikkat (busy / kharab / line off) yahan nahi — wo machine ke hisaab se alag aati hai."""
    from app.production_orders.routes import posted_issued_qty
    from app.production_orders.stage_material import gap_text, stage_material_gap
    reasons = []
    if order.status == "Released":
        if order.issue_status == "Not issued":
            reasons.append("Material is not issued yet")
        elif posted_issued_qty(order) <= 0.00005:
            reasons.append("Material issue is still a draft (post it)")
    gaps = stage_material_gap(order, stage.work_stage_id)
    if gaps:
        reasons.append(f"Material not fully issued ({gap_text(gaps)})")
    blocker = _routing().lab_qc_blocker(order, stage)
    if blocker is not None:
        reasons.append(f"{blocker.stage_name} needs a passed lab test with the TC uploaded")
    return reasons


def waiting_stages():
    """[{"order", "stage", "blockers"}] — Released / In production orders ka pehla na-hua stage jo Pending hai (yaani shuru hone ka intezaar).
    Ek baar nikaal ke saari machines ke liye kaam aata hai (dashboard har machine par alag se na dhundhe)."""
    orders = (ProductionOrder.query.filter(ProductionOrder.is_deleted == False, ProductionOrder.status.in_(QUEUE_STATUSES))
              .order_by(ProductionOrder.queue_position, ProductionOrder.id).all())
    out = []
    for order in orders:
        first_open = next((s for s in order.stages if s.status != "Done"), None)
        if first_open is None or first_open.status != "Pending":
            continue
        out.append({"order": order, "stage": first_open, "blockers": start_blockers(order, first_open)})
    return out


def plan_text(stage):
    # "Melting Furnace 1 (Line 1)" — plan wali machine(en) aur unki line
    names = []
    for row in stage.machines:
        machine = row.machine
        names.append(row.machine_name + (f" ({machine.line.name})" if machine is not None and machine.line else ""))
    return ", ".join(names)


def machine_error(order, stage, machine):
    """Is machine par ye stage chalane se roke aisi wajah (text) ya None. Plan wali machine ho to sirf active + busy dekhte hain (line off bhi chalta hai,
    jaisa Routing page par hamesha tha); badli machine ho to line / capacity bhi (routing.assign.target_error)."""
    in_plan = any(row.machine_id == machine.id for row in stage.machines)
    if not in_plan:
        return target_error(order, stage, machine)
    if machine.is_deleted or machine.status != "active":
        return f"{machine.name} is not available."
    info = busy_machines(order, stage).get(machine.id)
    return f"{machine.name} is {info['text']}." if info is not None else None


def eligible_orders_for_machine(machine, waiting=None):
    """Is (free) machine par kaun se orders ka stage chal sakta hai — Ready pehle, phir queue number, phir needed-by. Har item:
    order_id, stage_id, prod_no, product, status, batch_kg, home_line, same_line, in_plan, plan_text, plan_note, blockers, ready, own_line_waiting."""
    waiting = waiting if waiting is not None else waiting_stages()
    rows = []
    for item in waiting:
        order, stage = item["order"], item["stage"]
        if stage.work_stage_id != machine.work_stage_id:
            continue
        in_plan = any(row.machine_id == machine.id for row in stage.machines)
        blockers = list(item["blockers"])
        error = machine_error(order, stage, machine)
        if error:
            blockers.append(error)
        problem = _routing().stage_machine_problem(stage)
        rows.append({
            "order_id": order.id, "stage_id": stage.id, "prod_no": order.prod_no, "product": order.product.name if order.product else "",
            "status": order.status, "batch_kg": round((order.planned_qty or 0) * (order.unit_weight or 1), 2),
            "home_line": order.line.name if order.line else "", "home_line_id": order.line_id,
            "same_line": in_plan or (machine.line_id is not None and machine.line_id == order.line_id),
            "in_plan": in_plan, "stage_name": stage.stage_name, "plan_text": plan_text(stage),
            # Order abhi kyun ruka hai: plan wali machine busy / kharab ho to uska text; free ho to None
            "plan_note": problem["names"] if problem is not None else None,
            "position": order.queue_position, "needed_by": order.needed_by_date.strftime("%d %b") if order.needed_by_date else "",
            "blockers": blockers, "ready": not blockers,
            "_sort": (bool(blockers), order.queue_position if order.queue_position is not None else 10 ** 9,
                      order.needed_by_date.toordinal() if order.needed_by_date else 10 ** 9, order.prod_no)})
    rows.sort(key=lambda r: r["_sort"])
    ready_own = [r for r in rows if r["ready"] and r["same_line"]]
    for r in rows:
        # Is machine ki apni line ka koi aur order tayyar khada ho aur hum doosri line ka le rahe hon to warning + wajah (flow rule 4)
        r["own_line_waiting"] = [o["prod_no"] for o in ready_own if o["order_id"] != r["order_id"]] if not r["same_line"] else []
        del r["_sort"]
    return rows


def tile_waiting(machine, waiting):
    """Free machine ke tile ke liye: pehla ready order (ya None) aur kitne ready orders hain."""
    if machine.status != "active":
        return None
    ready = [r for r in eligible_orders_for_machine(machine, waiting) if r["ready"]]
    if not ready:
        return None
    return {"prod_no": ready[0]["prod_no"], "line": ready[0]["home_line"], "count": len(ready), "same_line": ready[0]["same_line"]}


def start_requirements(machine, order, stage):
    """Start form ko kya poochna padega (reasons) is machine par — machine tentative badal ke asli checks chalate hain. CALLER db.session.rollback() KARE (kuch save nahi hota).
    Wapas dict: clash / wait / cast / waste / under (har ek None ya text), in_plan, own_line_waiting."""
    routing = _routing()
    in_plan = any(row.machine_id == machine.id for row in stage.machines)
    if not in_plan:
        assign_machine(stage, machine, kind="assign")
    clash = routing.stage_clash(order, stage, routing.in_production_orders())
    wait = routing.wait_payload(routing.metal_wait(order, stage))
    is_melt = routing.side_stage_info(order, stage) is None and bool(stage.work_stage and stage.work_stage.is_batch)
    waste = routing.waste_payload(routing.melt_plan(order, stage, routing.melt_kg(stage))) if routing.side_stage_info(order, stage) is None else None
    cast = routing.cast_payload(routing.casting_ahead(order, stage)) if is_melt else None
    under = None
    lines = []
    if order.status == "Released":
        from app.production_lines.status import line_board
        from app.production_orders.routes import order_line_gap
        # Purane order jis par line chuni hi nahi thi: Start par line chunni padti hai (order banate waqt chuni ho to ye khaali rehta hai)
        if not order.line_id:
            lines = [{"id": row["id"], "name": row["name"]} for row in line_board(today_ist())]
        chosen, gap, _error = order_line_gap(order, lines[0]["id"] if len(lines) == 1 else None, today_ist())
        if chosen is not None and gap > 0.0001:
            batch_kg = (order.planned_qty or 0) * (order.unit_weight or 1)
            under = (f"{chosen['name']} can make {chosen['capacity']:g} KG a day but only {chosen['left_kg'] + batch_kg:g} KG is planned. "
                     f"Write why {gap:g} KG of its capacity stays unused.")
    return {"clash": clash["message"] if clash else None, "wait": wait if (wait and wait["over"]) else None,
            "cast": cast if (cast and cast["needs_reason"]) else None, "waste": waste, "under": under, "lines": lines, "in_plan": in_plan,
            "heat": bool(is_melt and stage.melt_group_id and len(routing.melt_members(stage)) > 1)}


def assign_and_start(machine, order, form):
    """Dashboard ka Assign & Start: (True, message) ya (False, error). Commit nahi karta; fail par caller rollback kare (ek hi transaction).
    Released order ho to pehle machine badli jaati hai (taaki schedule is machine ke hisaab se bane), phir order Start, phir stage Start."""
    from app.production_orders.routes import start_order
    routing = _routing()
    if order.is_deleted or order.status not in QUEUE_STATUSES:
        return False, f"{order.prod_no} is not waiting to start."
    stage = next((s for s in order.stages if s.status != "Done"), None)
    if stage is None or stage.status != "Pending":
        return False, f"{order.prod_no} has no stage waiting to start."
    if stage.work_stage_id != machine.work_stage_id:
        return False, f"{machine.name} cannot run {stage.stage_name} (it is a different kind of machine)."
    blockers = start_blockers(order, stage)
    if blockers:
        return False, f"{order.prod_no} cannot start yet: " + "; ".join(blockers) + "."
    reason = (form.get("assign_reason") or "").strip()[:150]
    row = next((r for r in eligible_orders_for_machine(machine) if r["order_id"] == order.id), None)
    if row is not None and row["own_line_waiting"] and len(reason) < 3:
        return False, (f"{machine.name} belongs to {machine.line.name if machine.line else 'another line'}, and its own order {', '.join(row['own_line_waiting'])} is also ready. "
                       f"Write why {order.prod_no} goes first (for example the other order is waiting for something).")
    in_plan = any(r.machine_id == machine.id for r in stage.machines)
    if order.status == "Released":
        assigned_note = ""
        if not in_plan:
            error = target_error(order, stage, machine)
            if error:
                return False, f"{stage.stage_name} cannot start: {error}"
            old_names = plan_text(stage)
            assign_machine(stage, machine, kind="assign", reason=reason)
            assigned_note = f"Machine changed at start: {old_names} -> {machine.name}" + (f", reason: {reason}" if reason else "")
        ok, message = start_order(order, form.get("line_id", type=int), form.get("under_reason") or "")
        if not ok:
            return False, message
        ok2, message2 = routing.start_stage(stage, order, form, target_machine_id=machine.id, kind="assign", assigned_note=assigned_note)
        return ok2, (message + " " + message2) if ok2 else message2
    return routing.start_stage(stage, order, form, target_machine_id=machine.id, kind="assign")


def queueable_orders_for_machine(machine):
    """Phase 2: abhi start kiye bina Released order ka plan is machine par karna ("Plan on this machine"). Sirf Released orders (unki dates queue se
    live bani hain, to badalne par sab dobara ban jaati hain). In production order ka stage Start par hi machine badalta hai.
    Wapas [{order_id, prod_no, product, stage_name, plan_text, home_line, batch_kg, blockers}]."""
    orders = (ProductionOrder.query.filter(ProductionOrder.is_deleted == False, ProductionOrder.status == "Released")
              .order_by(ProductionOrder.queue_position, ProductionOrder.id).all())
    rows = []
    for order in orders:
        stage = next((s for s in order.stages if s.work_stage_id == machine.work_stage_id and s.status == "Pending"), None)
        if stage is None or any(r.machine_id == machine.id for r in stage.machines):
            continue
        error = target_error(order, stage, machine, allow_busy=True)
        rows.append({"order_id": order.id, "prod_no": order.prod_no, "product": order.product.name if order.product else "",
                     "stage_name": stage.stage_name, "plan_text": plan_text(stage), "home_line": order.line.name if order.line else "",
                     "batch_kg": round((order.planned_qty or 0) * (order.unit_weight or 1), 2), "blockers": [error] if error else []})
    return rows


def queue_assign(machine, order, reason=""):
    """Released order ke is machine wale stage ka plan is machine par karo (start nahi). (True, message) ya (False, error). Commit caller karta hai;
    yahan sirf plan badalta hai aur queue ki dates (non-frozen sab orders ki) dobara likhta hai."""
    from app.production_orders.scheduler import persist_schedule
    if order.is_deleted or order.status != "Released":
        return False, f"{order.prod_no} is not a released order. An order already in production changes machine only when its stage is started."
    stage = next((s for s in order.stages if s.work_stage_id == machine.work_stage_id and s.status == "Pending"), None)
    if stage is None:
        return False, f"{order.prod_no} has no {machine.work_stage.name if machine.work_stage else 'matching'} stage waiting."
    if any(r.machine_id == machine.id for r in stage.machines):
        return False, f"{stage.stage_name} of {order.prod_no} is already planned on {machine.name}."
    error = target_error(order, stage, machine, allow_busy=True)
    if error:
        return False, f"Cannot plan {stage.stage_name} on {machine.name}: {error}"
    old_names = plan_text(stage)
    assign_machine(stage, machine, kind="queue", reason=(reason or "").strip()[:150])
    persist_schedule(today_ist())
    return True, f"{stage.stage_name} of {order.prod_no} is now planned on {machine.name} (was {old_names}). Its dates were worked out again."
