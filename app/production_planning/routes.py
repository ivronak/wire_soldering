# Production planning (client meeting 2, #6): order form me line / machine nahi chunte; yahan production manager Draft orders ko dekhta hai
# (expected delivery, material, late?), Plan se line + machines chunta hai aur phir Release karta hai.
# Plan ka asli editor Production order page ka Reschedule drawer hi hai (?plan=<id>&back=planning se seedha khulta hai) — dobara nahi banaya.
from flask import Blueprint, render_template, request

from app.production_orders.routes import bundle_counts
from app.production_orders.scheduler import live_schedule, today_ist

production_planning_bp = Blueprint("production_planning", __name__, template_folder="templates")


def draft_split(queue):
    # Queue ke Draft orders: (planning baaki, plan pakka — release ke liye tayyar)
    drafts = [o for o in queue if o.status == "Draft"]
    return [o for o in drafts if not o.plan_confirmed], [o for o in drafts if o.plan_confirmed]


@production_planning_bp.route("/production_planning")
def production_planning_page():
    tab = request.args.get("tab", "needs")
    if tab not in ("needs", "ready"):
        tab = "needs"
    queue, materials, schedule = live_schedule()
    needs, ready = draft_split(queue)
    shown = needs if tab == "needs" else ready
    late = len([o for o in needs + ready if o.needed_by_date and schedule.get(o.id) and schedule[o.id]["end"] > o.needed_by_date])
    return render_template("production_planning.html", active_nav="production_planning", tab=tab, orders=shown, bundles=bundle_counts(), schedule=schedule, materials=materials,
                           needs_count=len(needs), ready_count=len(ready), late_count=late, today=today_ist())
