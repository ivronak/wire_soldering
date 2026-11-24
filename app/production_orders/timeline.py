# Production queue ka Timeline (Gantt) view: har order ya har machine ek row, stages / orders din-wise bars.
# Sirf dikhane ke liye data banata hai (kuch save nahi karta). Dates scheduler.live_schedule() se aati hain, din Monday-Saturday (Sunday off).
from datetime import timedelta

# Stage / order ke rang (bg, border, text) — ek hi stage hamesha ek hi rang me dikhta hai
# Rang theme.js ke categorical tokens (cat2, cat7, cat1, cat4, cat6, cat5, cat3) + ek extra dark indigo se hain.
# Jaan-boojh ke red / green / amber / royal-blue nahi liye: woh status aur brand ke liye reserved hain, lane ka matlab "status" nahi hota.
PALETTE = [
    ("#E6F6F8", "#B2DDE4", "#0E7490"),   # cat2 cyan
    ("#F6EEE6", "#E3CDB6", "#8A5A2B"),   # cat7 brown
    ("#EEF0FD", "#C7CCF5", "#4338CA"),   # cat1 indigo
    ("#FAEAFB", "#EBC3F0", "#A21CAF"),   # cat4 magenta
    ("#EEF2F6", "#CBD5E1", "#475569"),   # cat6 slate
    ("#FCE9F1", "#F3BFD6", "#BE185D"),   # cat5 rose
    ("#F1EAFD", "#D9C8F7", "#6D28D9"),   # cat3 violet
    ("#E0E7FF", "#C7D2FE", "#3730A3"),   # extra: dark indigo
]


def _separate(bars):
    # Ek row ke bars jo ek hi din share karte hain (fractional din), unhe aadha-aadha baant do taaki ek ke upar ek na chadhein
    bars.sort(key=lambda b: b["left"])
    for index in range(1, len(bars)):
        prev, cur = bars[index - 1], bars[index]
        overlap = prev["left"] + prev["span"] - cur["left"]
        if overlap > 0:
            half = min(overlap / 2, prev["span"] / 2, cur["span"] / 2)
            prev["span"] -= half
            cur["left"] += half
            cur["span"] -= half
    return bars


def build_timeline(queue, schedule, today, by="order"):
    """queue: queue_orders() ki list, schedule: live_schedule() ka dict. by = "order" (ek order ek row) ya "machine" (ek machine ek row).
    Wapas None (kuch schedule nahi) ya {"days", "months", "rows", "today_i", "by"}."""
    scheduled = [o for o in queue if o.id in schedule]
    if not scheduled:
        return None
    dates = [today]
    for o in scheduled:
        for start, end in schedule[o.id]["windows"]:
            dates += [start, end]
        if o.needed_by_date:
            dates.append(o.needed_by_date)
    first, last = min(dates), max(dates) + timedelta(days=2)
    days = []
    day = first
    while day <= last:
        if day.weekday() != 6:
            days.append(day)
        day += timedelta(days=1)
    index = {d: i for i, d in enumerate(days)}

    def pos(d):
        # Sunday ya range ke bahar ki date ko paas ke kaam ke din par rakho
        while d not in index and d <= last:
            d += timedelta(days=1)
        return index.get(d, len(days) - 1)

    stage_ids = sorted({st.work_stage_id for o in scheduled for st in o.stages})
    stage_color = {sid: PALETTE[i % len(PALETTE)] for i, sid in enumerate(stage_ids)}
    order_color = {o.id: PALETTE[i % len(PALETTE)] for i, o in enumerate(scheduled)}

    rows = []
    if by == "machine":
        machines = {}
        for o in scheduled:
            for st, (start, end) in zip(o.stages, schedule[o.id]["windows"]):
                for m in st.machines:
                    entry = machines.setdefault(m.machine_id, {"name": m.machine_name, "order": (st.work_stage.sort_order if st.work_stage else 0, m.machine_name), "bars": []})
                    left = pos(start)
                    bg, border, text = order_color[o.id]
                    entry["bars"].append({"left": float(left), "span": float(pos(end) - left + 1), "title": f"{o.prod_no} · {st.stage_name}",
                                          "label": o.prod_no, "sub": st.stage_name, "bg": bg, "border": border, "text": text,
                                          "tip": f"{o.prod_no} — {st.stage_name}: {start.strftime('%d %b')} to {end.strftime('%d %b')}"})
        for entry in sorted(machines.values(), key=lambda e: e["order"]):
            rows.append({"label": entry["name"], "sub": "", "status": None, "needed_i": None, "bars": _separate(entry["bars"])})
    else:
        for o in scheduled:
            bars = []
            for st, (start, end) in zip(o.stages, schedule[o.id]["windows"]):
                left = pos(start)
                bg, border, text = stage_color[st.work_stage_id]
                machines = ", ".join(m.machine_name for m in st.machines)
                bars.append({"left": float(left), "span": float(pos(end) - left + 1), "title": st.stage_name, "label": st.stage_name, "sub": "",
                             "bg": bg, "border": border, "text": text,
                             "tip": f"{st.stage_name} ({machines}): {start.strftime('%d %b')} to {end.strftime('%d %b')}"})
            rows.append({"label": o.prod_no, "sub": o.product.name if o.product else "", "status": o.status,
                         "needed_i": pos(o.needed_by_date) if o.needed_by_date else None, "bars": _separate(bars)})

    today_i = pos(today)
    day_cells = []
    months = []
    for i, d in enumerate(days):
        day_cells.append({"dow": d.strftime("%a"), "num": d.day, "is_today": i == today_i, "week_start": d.weekday() == 0})
        label = d.strftime("%b %Y")
        if months and months[-1]["label"] == label:
            months[-1]["span"] += 1
        else:
            months.append({"label": label, "span": 1})
    legend = []
    if by == "order":
        names = {}
        for o in scheduled:
            for st in o.stages:
                names.setdefault(st.work_stage_id, (st.stage_name, stage_color[st.work_stage_id]))
        legend = [{"name": n, "bg": c[0], "border": c[1]} for sid, (n, c) in sorted(names.items())]
    return {"days": day_cells, "months": months, "rows": rows, "today_i": today_i, "by": by, "legend": legend, "count": len(days)}
