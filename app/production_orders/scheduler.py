# Production queue ka scheduler: open orders ko priority (queue position) ke order me machines par bitha ke har order ka
# "kab start, kab tak tayyar" nikalta hai. Pehla order pehle machines leta hai, doosra tab jab uski machines free hon, aur isi tarah.
# Raw material ka hisaab materials.py se aata hai (RM kam ho to order PO ke aane tak ruk jaata hai).
#
# Rules (user ke saath tay, 2026-10-19):
#   * Order ke stages ek ke baad ek; ek stage tab shuru jab pichhla stage khatam AUR us stage ki chuni saari machines free.
#   * Time "kaam ke din" me naapte hain (Monday-Saturday, Sunday off) — planning.py ke WEEKLY_OFF se.
#   * "In production" order frozen hai: uski dates start dabate waqt save hoti hain, baaki orders un ke aas-paas chalte hain.
#   * Ye sirf hisaab hai. Order list live isi se dikhti hai; DB me dates tab likhte hain jab queue badalti hai (persist_schedule).
import math
from datetime import datetime, timedelta

from app.extensions import db
from app.models import ProductionOrder
from app.production_orders.materials import check_materials
from app.production_orders.planning import add_working_days, next_working_day

OPEN_STATUSES = ("Draft", "Released", "In production")


def now_ist():
    # Abhi ka IST waqt (naive datetime) — stage start / end ke timestamp ke liye
    return datetime.utcnow() + timedelta(hours=5, minutes=30)


def today_ist():
    # Server UTC me chalta hai; ghar ka din India (IST) ka chahiye
    return (datetime.utcnow() + timedelta(hours=5, minutes=30)).date()


def working_index(origin, day):
    # origin (pehla kaam ka din) se day tak kitne kaam ke din aage hai (origin = 0). Pehle ka din 0 ginte hain.
    origin = next_working_day(origin)
    day = next_working_day(day)
    count = 0
    while origin < day:
        origin = next_working_day(origin + timedelta(days=1))
        count += 1
    return count


def date_at(origin, index):
    return add_working_days(origin, index + 1)


def schedule_stages(stage_specs, start_pos, machine_free):
    """stage_specs: [{"days": float, "machine_ids": [...]}] (order me). start_pos: kaam ke din (float) se pehle shuru nahi.
    machine_free: {machine_id: position} — badalta hai (ye order ke baad machines kab free). Wapas: [(start_pos, end_pos)] har stage ka."""
    position = start_pos
    windows = []
    for spec in stage_specs:
        free = max([machine_free.get(machine_id, 0.0) for machine_id in spec["machine_ids"]] or [0.0])
        start = max(position, free)
        end = start + spec["days"]
        windows.append((start, end))
        for machine_id in spec["machine_ids"]:
            machine_free[machine_id] = end
        position = end
    return windows


def _window_dates(origin, start_pos, end_pos):
    # Position (float) ko date window me badlo. Aadha din bhi us din ko busy ginta hai (isliye floor / ceil).
    first = int(math.floor(start_pos + 1e-9))
    last = max(int(math.ceil(end_pos - 1e-9)) - 1, first)
    return date_at(origin, first), date_at(origin, last)


def queue_orders():
    # Queue ka order: pehle "In production" (frozen), phir baaki queue_position se. Cancelled / delete wale nahi.
    open_orders = ProductionOrder.query.filter(ProductionOrder.is_deleted == False, ProductionOrder.status.in_(OPEN_STATUSES)).all()
    key = lambda o: (o.queue_position if o.queue_position is not None else 10 ** 9, o.id)
    frozen = sorted([o for o in open_orders if o.status == "In production"], key=key)
    waiting = sorted([o for o in open_orders if o.status != "In production"], key=key)
    return frozen + waiting


def _stage_specs(order):
    batch_kg = order.planned_qty * order.unit_weight
    specs = []
    for stage in order.stages:
        if not stage.daily_capacity or stage.daily_capacity <= 0 or not stage.machines:
            return None
        specs.append({"days": batch_kg / stage.daily_capacity, "machine_ids": [m.machine_id for m in stage.machines]})
    return specs or None


def live_schedule(today=None, ordered=None, earliest_override=None):
    """Poori queue ka live hisaab. Wapas (ordered, materials, schedule):
    schedule[order_id] = {"start", "end", "windows": [(d1, d2)], "frozen", "waits_for_material": date|None, "working_days"}.
    Plan-less order (stages nahi) schedule me nahi aata. earliest_override={order_id: date}: "Start production" ke waqt us order ko aaj se shuru maano."""
    today = today or today_ist()
    origin = next_working_day(today)
    ordered = ordered if ordered is not None else queue_orders()
    earliest_override = earliest_override or {}
    materials = check_materials(ordered)
    machine_free = {}
    schedule = {}
    for order in ordered:
        stored = [(s.start_date, s.end_date) for s in order.stages]
        frozen = order.status == "In production" and order.id not in earliest_override and stored and all(a and b for a, b in stored)
        if frozen:
            # Frozen order: save hui dates hi sach; machines un dates tak busy
            for stage in order.stages:
                end_pos = 0.0 if stage.end_date < origin else working_index(origin, stage.end_date) + 1.0
                for machine in stage.machines:
                    machine_free[machine.machine_id] = max(machine_free.get(machine.machine_id, 0.0), end_pos)
            schedule[order.id] = {"start": order.stages[0].start_date, "end": order.stages[-1].end_date, "windows": stored,
                                  "frozen": True, "waits_for_material": None, "working_days": order.planned_days}
            continue
        specs = _stage_specs(order)
        if not specs:
            continue
        earliest = earliest_override.get(order.id) or order.earliest_start_date or order.order_date
        material_date = materials.get(order.id, {}).get("ready_date")
        wanted = max([d for d in (earliest, material_date, today) if d])
        start_pos = float(working_index(origin, wanted))
        positions = schedule_stages(specs, start_pos, machine_free)
        windows = [_window_dates(origin, a, b) for a, b in positions]
        total_days = sum(spec["days"] for spec in specs)
        schedule[order.id] = {"start": windows[0][0], "end": windows[-1][1], "windows": windows, "frozen": False,
                              "waits_for_material": material_date if (material_date and material_date > max(earliest or today, today)) else None,
                              "working_days": max(int(math.ceil(total_days - 1e-9)), 1)}
    return ordered, materials, schedule


def persist_schedule(today=None):
    # Queue badalne par (naya order, reorder, cancel, reschedule) har order ki dates DB me likh do. Frozen orders ko nahi chhedte.
    ordered, _materials, schedule = live_schedule(today)
    for order in ordered:
        info = schedule.get(order.id)
        if not info or info["frozen"]:
            continue
        order.planned_start_date = info["start"]
        order.planned_end_date = info["end"]
        for stage, (start, end) in zip(order.stages, info["windows"]):
            stage.start_date = start
            stage.end_date = end
    db.session.flush()


def renumber_queue():
    # Queue ke open orders ko 1, 2, 3... me likh do (gaps / purani values theek). Order wahi jo queue_orders() batata hai.
    for position, order in enumerate(queue_orders(), start=1):
        order.queue_position = position
    db.session.flush()
