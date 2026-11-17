# Production planning (client meeting 2, #6 + C1 16 Nov): factory / production manager ka page. Production order page ab sirf order daalne + status ke liye hai;
# queue ka saara kaam yahin: Plan (line + machines), Release, queue me upar-neeche (▲▼ / Make first), Reschedule, Start (line chuno) aur Cancel.
# Drawers (Plan / Start / Cancel) ke HTML + JS shared partials me hain (production_orders/templates/_plan_*.html, _cancel_modal.html).
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import MachineExtraHours, Machines
from app.production_orders.planning import WEEKLY_OFF

from app.production_lines.status import line_board
from app.production_orders.routes import bundle_counts, progress_info, resched_data
from app.production_orders.scheduler import live_schedule, persist_schedule, today_ist
from app.production_planning.day_plan import machine_rows, plan_day
from app.production_orders.stage_material import later_stage_gaps

production_planning_bp = Blueprint("production_planning", __name__, template_folder="templates")


def draft_split(queue):
    # Queue ke Draft orders: (planning baaki, plan pakka — release ke liye tayyar)
    drafts = [o for o in queue if o.status == "Draft"]
    return [o for o in drafts if not o.plan_confirmed], [o for o in drafts if o.plan_confirmed]


@production_planning_bp.route("/production_planning")
def production_planning_page():
    tab = request.args.get("tab", "needs")
    if tab not in ("needs", "ready", "queue", "tomorrow"):
        tab = "needs"
    today = today_ist()
    queue, materials, schedule = live_schedule()
    # C10: "Tomorrow" tab — kal (ya chuna hua aage ka din) kaun si machine par kya chalega, khali machine, extra shift
    day, day_rows, day_kpi = None, [], {}
    if tab == "tomorrow":
        try:
            asked = datetime.strptime(request.args.get("date", ""), "%Y-%m-%d").date()
        except ValueError:
            asked = None
        day = plan_day(today, asked)
        day_rows = machine_rows(day, queue, schedule)
        day_kpi = {"running": len([r for r in day_rows if r["jobs"]]), "idle": len([r for r in day_rows if not r["jobs"]]),
                   "extra": len([r for r in day_rows if r["extra_hours"] > 0])}
    needs, ready = draft_split(queue)
    # Queue tab: Release ho chuke aur chalte hue orders (queue ke order me)
    running = [o for o in queue if o.status in ("Released", "In production")]
    shown = {"needs": needs, "ready": ready, "queue": running, "tomorrow": []}[tab]
    open_orders = needs + ready + running
    late = len([o for o in open_orders if o.needed_by_date and schedule.get(o.id) and schedule[o.id]["end"] > o.needed_by_date])
    need_material = len([o for o in open_orders if materials.get(o.id, {}).get("status") in ("making", "coming", "buy")])
    progress, stage_now = progress_info(queue, schedule, today)
    return render_template(
        "production_planning.html", active_nav="production_planning", tab=tab, orders=shown, bundles=bundle_counts(), schedule=schedule, materials=materials,
        needs_count=len(needs), ready_count=len(ready), queue_count=len(running), late_count=late, material_count=need_material, today=today,
        progress=progress, stage_now=stage_now, day=day, day_rows=day_rows, day_kpi=day_kpi,
        # C7: baad ke stage ka maal abhi issue nahi hua to "wait karega" likha aata hai (Released / In production orders)
        issue_gaps={o.id: later_stage_gaps(o) for o in shown if o.status in ("Released", "In production")},
        # Plan / Reschedule drawer ka data aur Start ke liye lines ki live status
        resched=resched_data(shown), line_board=line_board(today),
    )


@production_planning_bp.route("/production_planning/extra_hours", methods=["POST"])
def production_planning_extra_hours():
    """C10: ek machine ka ek din ka extra (raat ki) shift. 0 daalo to wo din wapas normal. Save ke baad queue ki dates dobara bante hain
    (jo order abhi chal rahe hain unki dates frozen rehti hain)."""
    today = today_ist()
    try:
        day = datetime.strptime(request.form.get("work_date", ""), "%Y-%m-%d").date()
    except ValueError:
        flash("Choose a valid date.", "error")
        return redirect(url_for("production_planning.production_planning_page", tab="tomorrow"))
    back = redirect(url_for("production_planning.production_planning_page", tab="tomorrow", date=day.isoformat()))
    machine = db.session.get(Machines, request.form.get("machine_id", type=int) or 0)
    if machine is None or machine.is_deleted or machine.status != "active":
        flash("Machine not found or not active.", "error")
        return back
    if day < today:
        flash("Extra hours can only be set for today or a later day.", "error")
        return back
    if day.weekday() == WEEKLY_OFF:
        flash("That day is the weekly off. Choose a working day.", "error")
        return back
    hours = request.form.get("extra_hours", type=float)
    normal = machine.hours_per_day or 8
    if hours is None or hours < 0:
        flash("Enter the extra hours (0 or more).", "error")
        return back
    if normal + hours > 24:
        flash(f"{machine.name} already runs {normal:g} h a day; extra hours can be at most {24 - normal:g}.", "error")
        return back
    reason = (request.form.get("reason") or "").strip()[:120]
    row = MachineExtraHours.query.filter_by(machine_id=machine.id, work_date=day).first()
    if row is None:
        row = MachineExtraHours(machine_id=machine.id, work_date=day)
        db.session.add(row)
    row.extra_hours = round(hours, 2)
    row.reason = reason or None
    db.session.flush()
    persist_schedule()
    db.session.commit()
    if hours > 0:
        flash(f"{machine.name}: {hours:g} extra hours on {day.strftime('%d %b')}. Order dates are worked out again.", "success")
    else:
        flash(f"{machine.name}: extra shift on {day.strftime('%d %b')} removed.", "success")
    return back
