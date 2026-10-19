# Production order ka plan: kitne ghante / din lagenge, kab tak tayyar, roz ka maximum kitna.
# Sirf hisaab karta hai (kuch save nahi karta). Route (routes.py) aur form ka JS (production_orders.html, planFor) yahi formula use karte hain.
#
# Rules (user ke saath tay, 2026-10-19):
#   * Stage ek ke baad ek chalte hain: order ka kul time = saare stages ke time ka jod.
#   * Ek stage ki capacity = us stage ke chune hue machines ki capacity ka jod (KG per hour).
#   * Stage ke ghante = batch KG / stage ki capacity per hour. Stage ke din = batch KG / stage ki daily capacity (capacity x din ke ghante).
#   * Roz ka maximum = sabse dheeme (bottleneck) stage ki daily capacity.
#   * Kaam ke din Monday-Saturday (Sunday off). Ye ek hi jagah (WEEKLY_OFF) likha hai; baad me Company / calendar setting banegi.
import math
from datetime import timedelta

WEEKLY_OFF = 6          # Python weekday(): Monday = 0 ... Sunday = 6


def next_working_day(day):
    while day.weekday() == WEEKLY_OFF:
        day = day + timedelta(days=1)
    return day


def add_working_days(start, count):
    # start = pehla kaam ka din. count din ke baad ka aakhri kaam ka din (count = 1 ho to wahi din).
    day = next_working_day(start)
    remaining = count - 1
    while remaining > 0:
        day = next_working_day(day + timedelta(days=1))
        remaining -= 1
    return day


def plan_stages(batch_kg, stages, start_date):
    """batch_kg: kitne KG banana hai. stages: [{"stage_id", "name", "machines": [{"id", "name", "per_hour", "hours_per_day"}]}] (order me).
    Wapas: dict — har stage ka hisaab, total ghante, kaam ke din, start / end date, roz ka maximum (KG) aur kaunsa stage dheema hai."""
    rows = []
    raw_days = []           # bina round kiye din (window ka hisaab inhi se, taaki rounding se din na khisake)
    total_hours = 0.0
    total_days = 0.0
    bottleneck = None
    for stage in stages:
        per_hour = sum(m["per_hour"] for m in stage["machines"])
        per_day = sum(m["per_hour"] * m["hours_per_day"] for m in stage["machines"])
        hours = batch_kg / per_hour if per_hour > 0 else 0.0
        days = batch_kg / per_day if per_day > 0 else 0.0
        total_hours += hours
        total_days += days
        row = {"stage_id": stage["stage_id"], "name": stage["name"], "machines": stage["machines"],
               "per_hour": round(per_hour, 4), "per_day": round(per_day, 4), "hours": round(hours, 2), "days": round(days, 2)}
        rows.append(row)
        raw_days.append(days)
        if per_day > 0 and (bottleneck is None or per_day < bottleneck["per_day"]):
            bottleneck = row
    working_days = max(int(math.ceil(total_days - 1e-9)), 1) if rows else 0
    # Har stage ka din-wise window: pichhle stages ke din jod ke us stage ka pehla / aakhri kaam ka din.
    # Aadha din bhi us din ko "busy" ginta hai (day-level hisaab, conservative) — machine clash isi se dekhte hain.
    passed = 0.0
    for row, days in zip(rows, raw_days):
        first = int(math.floor(passed + 1e-9))
        passed += days
        last = max(int(math.ceil(passed - 1e-9)) - 1, first)
        row["start_date"] = add_working_days(start_date, first + 1)
        row["end_date"] = add_working_days(start_date, last + 1)
    start = next_working_day(start_date) if rows else None
    end = add_working_days(start_date, working_days) if rows else None
    return {
        "stages": rows,
        "total_hours": round(total_hours, 2),
        "working_days": working_days,
        "start_date": start,
        "end_date": end,
        "daily_capacity": round(bottleneck["per_day"], 2) if bottleneck else None,
        "bottleneck": bottleneck["name"] if bottleneck else None,
    }
