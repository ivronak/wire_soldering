# Stage timing clash lock (client meeting 2, change 10): Melting jaisa "garam" stage (Work Stage me Batch tick) ka maal pichhle order se
# agle stage (Ingot Casting) ki machine par kuch hi der me aane wala ho, aur us machine par koi doosra lamba kaam shuru kar diya jaye,
# to garam maal rukke ghatt jayega. Isliye aisa kaam shuru hone se pehle roka jaata hai (kaam us gap me poora ho sakta ho to allow).
# Sirf padhta hai, kuch save nahi karta. Use: routing_start (lock), dashboard (machine par "incoming" dikhana).
from datetime import timedelta

from app.models import Machines
from app.production_orders.scheduler import now_ist
from app.routing.busy import busy_machines


def hours_text(minutes):
    # 135 -> "2 h 15 m", 40 -> "40 m"
    minutes = max(int(round(minutes)), 0)
    hours, mins = divmod(minutes, 60)
    return f"{hours} h {mins:02d} m" if hours else f"{mins} m"


def hot_handoffs(orders, now=None):
    """[{machine_id, machine_name, order, stage, prev_stage, minutes_left, waiting}] — jin orders ka garam stage chal raha ya abhi khatam hua hai aur agla stage
    (Pending) jis machine par jaayega. minutes_left = garam stage ke plan ke hisaab se kitni der me maal aayega (0 = abhi / der ho chuki).
    Plan ghante ka pata na ho to us order ko chhod dete hain (andaza lagana galat hoga)."""
    now = now or now_ist()
    out = []
    for order in orders:
        stages = list(order.stages)
        for index in range(1, len(stages)):
            stage, prev = stages[index], stages[index - 1]
            if stage.status != "Pending" or not (prev.work_stage and prev.work_stage.is_batch):
                continue
            if prev.status == "In progress":
                if not prev.started_at or not prev.planned_hours:
                    continue
                left = prev.planned_hours * 60 - (now - prev.started_at).total_seconds() / 60
                left = max(left, 0.0)
            elif prev.status == "Done":
                left = 0.0              # garam maal taiyar hai, ab casting ka intezaar (waiting)
            else:
                continue
            wait = metal_wait(order, stage, now) if prev.status == "Done" else None
            for row in stage.machines:
                out.append({"machine_id": row.machine_id, "machine_name": row.machine_name, "order": order, "stage": stage, "prev_stage": prev,
                            "minutes_left": round(left, 1), "waiting": prev.status == "Done", "wait": wait})
    return out


def metal_wait(order, stage, now=None):
    """C12: stage Pending hai aur uska pichhla stage (Melting) Done hai jiske Work Stage me "Max wait before next stage (minutes)" bhara hai
    to garam maal kab se ruka hai: {since, minutes, limit, over, prev_name}. Warna None. Timer pichhle stage ke completed_at se chalta hai
    (beech ka Lab QC intezaar bhi ginta hai, kyunki maal tab bhi thanda ho raha hai)."""
    if stage.status != "Pending":
        return None
    now = now or now_ist()
    previous = [s for s in order.stages if s.sort_order < stage.sort_order]
    if not previous:
        return None
    prev = previous[-1]
    limit = prev.work_stage.max_wait_minutes if prev.work_stage else None
    if prev.status != "Done" or not prev.completed_at or not limit:
        return None
    minutes = max((now - prev.completed_at).total_seconds() / 60, 0.0)
    return {"since": prev.completed_at, "minutes": round(minutes, 1), "limit": int(limit), "over": minutes > limit, "prev_name": prev.stage_name}


def stage_clash(order, stage, orders, now=None):
    """Is stage ko abhi shuru karne par kisi doosre order ke garam maal se takrao ho to {message, machine_name, other_order, minutes_left} warna None.
    Takrao tab jab is stage ka plan time (planned_hours) us maal ke aane ke time se zyada ho (gap me poora nahi hota)."""
    if not stage.planned_hours:
        return None
    needed = stage.planned_hours * 60
    mine = {row.machine_id for row in stage.machines}
    worst = None
    for h in hot_handoffs([o for o in orders if o.id != order.id], now):
        if h["waiting"]:
            continue            # doosre ka maal pehle se taiyar rakha hai (dono garam): pehle aao pehle pao, yahan nahi roka jaata
        if h["machine_id"] in mine and h["minutes_left"] < needed - 1e-6:
            if worst is None or h["minutes_left"] < worst["minutes_left"]:
                worst = h
    if worst is None:
        return None
    when = "right now" if worst["minutes_left"] <= 0.5 else f"in about {hours_text(worst['minutes_left'])}"
    message = (f"{worst['machine_name']} is needed {when} for {worst['order'].prod_no}: its {worst['prev_stage'].stage_name} output goes to "
               f"{worst['stage'].stage_name}, and hot metal cannot wait. {stage.stage_name} of {order.prod_no} takes about {hours_text(needed)}, "
               f"so it would block the machine. Start it after {worst['order'].prod_no} has started {worst['stage'].stage_name}, or write a reason to start anyway.")
    return {"message": message, "machine_name": worst["machine_name"], "other_order": worst["order"].prod_no, "minutes_left": worst["minutes_left"]}


def casting_ahead(order, stage, start_at=None, now=None):
    """G14-4: Melting (batch stage) shuru karne se pehle dekho ki melt taiyar hone par agle stage (Ingot Casting) ki koi machine free hogi ya nahi.
    Melt taiyar hone ka time = start + planned_hours. Agle stage ki koi bhi chalu machine (kisi bhi line ki) us time tak free ho to None.
    Warna {message, delay_minutes, needs_reason, ready_at}: delay = sabse jaldi free hone wali machine us time ke kitne baad free hogi
    (hold par / free time pata nahi ho to delay None = pata nahi). needs_reason tab jab delay Work Stage ke "Max wait" se zyada ho (limit na ho to jab bhi delay)."""
    now = now or now_ist()
    if stage.status != "Pending" or not (stage.work_stage and stage.work_stage.is_batch) or not stage.planned_hours:
        return None
    later = [s for s in order.stages if s.sort_order > stage.sort_order]
    if not later or later[0].status != "Pending":
        return None
    nxt = later[0]
    machines = Machines.query.filter(Machines.work_stage_id == nxt.work_stage_id, Machines.is_deleted == False, Machines.status == "active").all()
    if not machines:
        return None             # koi chalu machine hi nahi: wo alag (G27) message deta hai
    ready_at = (start_at or now) + timedelta(hours=stage.planned_hours)
    busy = busy_machines(order, nxt)
    soonest = None              # (free_at, machine name, prod_no) — sabse jaldi free hone wali jiska time pata ho
    unknown = []
    for machine in machines:
        info = busy.get(machine.id)
        if info is None:
            return None         # ek machine abhi free hai: melt ke baad wahi chalegi
        if info["free_at"] is None:
            unknown.append(f"{machine.name} ({info['text']})")
        elif info["free_at"] <= ready_at:
            return None         # melt taiyar hone se pehle free ho jaayegi
        elif soonest is None or info["free_at"] < soonest[0]:
            soonest = (info["free_at"], machine.name, info["prod_no"])
    fmt = lambda d: d.strftime("%H:%M") if d.date() == now.date() else d.strftime("%d %b %H:%M")
    limit = stage.work_stage.max_wait_minutes
    if soonest is not None:
        delay = (soonest[0] - ready_at).total_seconds() / 60
        message = (f"This melt will be ready at about {fmt(ready_at)}, but every {nxt.stage_name} machine is busy then. The first to be free is "
                   f"{soonest[1]} (busy with {soonest[2]}) at about {fmt(soonest[0])}, so the molten metal would wait about {hours_text(delay)}.")
        needs = (not limit) or delay > limit
    else:
        delay = None
        message = (f"This melt will be ready at about {fmt(ready_at)}, but every {nxt.stage_name} machine is busy and none has a known free time: "
                   f"{', '.join(unknown)}. The molten metal may have to wait.")
        needs = True
    if limit and delay is not None and not needs:
        message += f" This is within the {limit} min limit for molten metal."
    return {"message": message, "delay_minutes": round(delay, 1) if delay is not None else None, "needs_reason": needs, "ready_at": ready_at,
            "next_name": nxt.stage_name}
