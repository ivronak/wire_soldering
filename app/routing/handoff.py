# Stage timing clash lock (client meeting 2, change 10): Melting jaisa "garam" stage (Work Stage me Batch tick) ka maal pichhle order se
# agle stage (Ingot Casting) ki machine par kuch hi der me aane wala ho, aur us machine par koi doosra lamba kaam shuru kar diya jaye,
# to garam maal rukke ghatt jayega. Isliye aisa kaam shuru hone se pehle roka jaata hai (kaam us gap me poora ho sakta ho to allow).
# Sirf padhta hai, kuch save nahi karta. Use: routing_start (lock), dashboard (machine par "incoming" dikhana).
from app.production_orders.scheduler import now_ist


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
            for row in stage.machines:
                out.append({"machine_id": row.machine_id, "machine_name": row.machine_name, "order": order, "stage": stage, "prev_stage": prev,
                            "minutes_left": round(left, 1), "waiting": prev.status == "Done"})
    return out


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
