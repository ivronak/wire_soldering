# C10: "Kal ka plan raat ko" — planning team raat ko dekhti hai ki kal (ya koi bhi aage ka kaam ka din) kaun si machine par kya chalega,
# kaun si machine khali hai, aur kahan extra (raat ki) shift lagani hai. Sirf hisaab: data live_schedule ki windows se aata hai.
from app.models import MachineExtraHours, Machines
from app.production_orders.planning import next_working_day


def plan_day(today, requested):
    # Dikhane ka din: requested (date) ho aur aaj se pehle ka na ho to wahi (Sunday ho to agla kaam ka din); warna kal (agla kaam ka din)
    from datetime import timedelta
    day = requested if requested and requested > today else today + timedelta(days=1)
    return next_working_day(day)


def machine_rows(day, queue, schedule):
    """Har active machine ka us din ka haal. Wapas list of dict: machine, line_name, jobs, normal_hours, extra_hours, reason.
    jobs = us din jis order ka jo stage is machine par chalna hai (Done stages nahi)."""
    jobs = {}
    for order in queue:
        info = schedule.get(order.id)
        if not info:
            continue
        for stage, (start, end) in zip(order.stages, info["windows"]):
            if stage.status == "Done" or not (start <= day <= end):
                continue
            for row in stage.machines:
                jobs.setdefault(row.machine_id, []).append({"prod_no": order.prod_no, "product": order.product.name if order.product else "",
                                                            "stage": stage.stage_name, "status": order.status, "order_id": order.id})
    extras = {r.machine_id: r for r in MachineExtraHours.query.filter_by(work_date=day).all()}
    machines = (Machines.query.filter(Machines.is_deleted == False, Machines.status == "active")
                .order_by(Machines.line_id, Machines.work_stage_id, Machines.name).all())
    rows = []
    for m in machines:
        extra = extras.get(m.id)
        rows.append({"machine": m, "line_name": m.line.name if m.line else "No line", "stage_name": m.work_stage.name if m.work_stage else "",
                     "jobs": jobs.get(m.id, []), "normal_hours": m.hours_per_day or 8,
                     "extra_hours": extra.extra_hours if extra else 0, "reason": (extra.reason if extra else "") or ""})
    return rows
