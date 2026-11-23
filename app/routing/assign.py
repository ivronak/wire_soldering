# Dashboard / Routing: kisi stage ko doosri (free) machine par chalane ke helpers — "Assign & Start" aur "Use this machine instead" dono yahin se.
# Line = order ka "home" label; machine asli resource hai: stage usi work stage ki kisi bhi Active machine par chal sakta hai, kisi bhi line ki
# (client ka rule: machine ek minute bhi khali nahi baithni chahiye). Plan wali machine ki row delete hoti hai, par uski copy
# production_order_stage_machine_changes me rehti hai (history + Cancel run par wapas). Ye file commit nahi karti — caller (route) karta hai.
from app.extensions import db
from app.models import Machines, ProductionLine, ProductionOrderStageMachine, ProductionOrderStageMachineChange
from app.production_orders.scheduler import now_ist
from app.routing.batch import melt_members, stage_kg
from app.routing.busy import busy_machines


def line_ok(machine):
    """Machine ki line is waqt chal rahi hai? (D6) Line band / delete ho to us line ki machine kisi aur order ko nahi di jaati.
    Production Lines bani hi nahi (purana setup) to har machine theek; lines bani hon aur machine kisi line me nahi to nahi."""
    if machine.line_id is None:
        return ProductionLine.query.filter_by(is_deleted=False).count() == 0
    line = machine.line
    return bool(line is not None and not line.is_deleted and line.is_active)


def machine_usable(machine):
    # Active, delete nahi hui, aur capacity numbers bhare hain (warna ghante nikalte nahi)
    return machine is not None and not machine.is_deleted and machine.status == "active" and (machine.capacity_per_hour or 0) > 0


def eligible_machines(order, stage, busy=None):
    """Is stage ke liye badli ki machines: usi work stage ki Active machine, jo plan me nahi, abhi busy nahi, aur jiski line chal rahi hai.
    Wapas [Machines]. (stage ki apni plan wali machines ko bahar rakhta hai — wo "badli" nahi, plan hi hain.)"""
    busy = busy if busy is not None else busy_machines(order, stage)
    planned = {row.machine_id for row in stage.machines}
    rows = Machines.query.filter(Machines.work_stage_id == stage.work_stage_id, Machines.is_deleted == False,
                                 Machines.status == "active").order_by(Machines.code).all()
    return [m for m in rows if m.id not in planned and m.id not in busy and machine_usable(m) and line_ok(m)]


def target_error(order, stage, machine, allow_busy=False):
    """Is machine par stage chalane se roke aisi wajah (English text) ya None. Plan wali machine ho to uski busy / down wali jaankari routing ka
    stage_machine_problem deta hai, yahan sirf "badli" machine ki jaanch hai. allow_busy=True: sirf queue me daalna hai (abhi start nahi), to busy chalti hai."""
    if machine is None or machine.is_deleted:
        return "That machine was not found."
    if machine.work_stage_id != stage.work_stage_id:
        return f"{machine.name} is not a {stage.stage_name} machine."
    if machine.status != "active":
        return f"{machine.name} is not available (it is not Active in the Machine master)."
    if not machine_usable(machine):
        return f"{machine.name} has no capacity set in the Machine master, so hours cannot be planned on it."
    if not line_ok(machine):
        return f"{machine.name} belongs to a production line that is switched off."
    info = None if allow_busy else busy_machines(order, stage).get(machine.id)
    if info is not None:
        return f"{machine.name} is {info['text']}."
    return None


def refresh_order_totals(order):
    # Order ke upar ke plan ke totals (kul ghante / din / bottleneck) stages ke naye numbers se dobara — machine badli to ye purane na rahein
    stages = [s for s in order.stages if s.planned_hours is not None]
    if not stages or len(stages) != len(order.stages):
        return
    order.planned_hours = round(sum(s.planned_hours for s in stages), 2)
    days = sum(s.planned_days or 0 for s in stages)
    order.planned_days = max(int(-(-days // 1)), 1)
    slowest = min((s for s in stages if s.daily_capacity), key=lambda s: s.daily_capacity, default=None)
    if slowest is not None:
        order.daily_capacity = round(slowest.daily_capacity, 2)
        order.bottleneck_stage = slowest.stage_name


def refresh_capacity(stage):
    # D1: machine badli to stage ka capacity / ghante / din naye machine rows se dobara nikalo (pehle purani machine ke numbers rah jaate the,
    # isliye waste / clash / free-time ka hisaab galat aata tha). Formula wahi jo planning.plan_stages ka hai.
    rows = list(stage.machines)
    per_hour = sum(r.capacity_per_hour or 0 for r in rows)
    per_day = sum((r.capacity_per_hour or 0) * (r.hours_per_day or 0) for r in rows)
    batch = stage_kg(stage)
    stage.capacity_per_hour = round(per_hour, 4)
    stage.daily_capacity = round(per_day, 4)
    stage.planned_hours = round(batch / per_hour, 2) if per_hour > 0 else None
    stage.planned_days = round(batch / per_day, 2) if per_day > 0 else None


def _log(stage, row, to_machine, kind, reason):
    db.session.add(ProductionOrderStageMachineChange(
        stage_id=stage.id, from_machine_id=row.machine_id, from_machine_name=row.machine_name,
        from_capacity_per_hour=row.capacity_per_hour, from_hours_per_day=row.hours_per_day,
        to_machine_id=to_machine.id if to_machine is not None else None, to_machine_name=to_machine.name if to_machine is not None else None,
        kind=kind, reason=(reason or "")[:150] or None, changed_at=now_ist().replace(microsecond=0),
        # "queue" (sirf plan badla, kaam start nahi hua) ko Cancel run par wapas nahi karte: wo ab order ka naya plan hai, sirf history ke liye likha
        reverted_at=now_ist().replace(microsecond=0) if kind == "queue" else None))


def drop_rows(stage, rows, kind, reason=None, to_machine=None):
    # Plan ki ye machine rows stage se hatao (kharab machine ya badli) — har ek ka log likhte hain
    for row in list(rows):
        _log(stage, row, to_machine, kind, reason)
        db.session.delete(row)


def settle(stage):
    # Rows badalne ke baad: DB me likho, stage.machines ki memory wali list ko naya karo (nahi to aage ke checks purani rows padhte hain), capacity dobara nikalo
    db.session.flush()
    db.session.expire(stage, ["machines"])
    refresh_capacity(stage)
    refresh_order_totals(stage.production_order)


def assign_machine(stage, machine, kind="assign", reason=None):
    """Stage ki saari plan machines ki jagah sirf `machine`. Combined melt ho to us melt ke sab members ek saath (wo ek hi furnace me hain).
    Wapas [stages jo badle]. Machine pehle se stage ki plan me ho (aur akeli ho) to kuch nahi badalta."""
    members = melt_members(stage) if (stage.work_stage and stage.work_stage.is_batch and stage.melt_group_id) else [stage]
    changed = []
    for member in members:
        rows = list(member.machines)
        if len(rows) == 1 and rows[0].machine_id == machine.id:
            continue
        drop_rows(member, rows, kind, reason, to_machine=machine)
        db.session.add(ProductionOrderStageMachine(stage_id=member.id, machine_id=machine.id, machine_name=machine.name,
                                                   capacity_per_hour=machine.capacity_per_hour or 0, hours_per_day=machine.hours_per_day or 8,
                                                   is_planned=True, used=False))
        settle(member)
        changed.append(member)
    return changed


def restore_planned(stage):
    """Cancel run: Start par machine badli thi to plan wali machine(en) wapas, aur badli wali hata do. Wapas kitni machine rows wapas aayin (0 = kuch badla nahi tha).
    Wahi machine ab kharab / busy ho sakti hai — usi ka alert Start par dobara aata hai, yahan sirf plan wapas karte hain."""
    changes = (ProductionOrderStageMachineChange.query.filter_by(stage_id=stage.id, reverted_at=None)
               .order_by(ProductionOrderStageMachineChange.id).all())
    if not changes:
        return 0
    now = now_ist().replace(microsecond=0)
    for row in list(stage.machines):
        if any(c.to_machine_id == row.machine_id for c in changes):
            db.session.delete(row)
    restored = 0
    have = {row.machine_id for row in stage.machines}
    for change in changes:
        if change.from_machine_id is not None and change.from_machine_id not in have:
            db.session.add(ProductionOrderStageMachine(stage_id=stage.id, machine_id=change.from_machine_id, machine_name=change.from_machine_name or "",
                                                       capacity_per_hour=change.from_capacity_per_hour or 0, hours_per_day=change.from_hours_per_day or 8,
                                                       is_planned=True, used=False))
            have.add(change.from_machine_id)
            restored += 1
        change.reverted_at = now
    settle(stage)
    return restored
