# Production planning (client meeting 2, #6 + C1 16 Nov): factory / production manager ka page. Production order page ab sirf order daalne + status ke liye hai;
# queue ka saara kaam yahin: Plan (line + machines), Release, queue me upar-neeche (▲▼ / Make first), Reschedule, Start (line chuno) aur Cancel.
# Drawers (Plan / Start / Cancel) ke HTML + JS shared partials me hain (production_orders/templates/_plan_*.html, _cancel_modal.html).
from flask import Blueprint, render_template, request

from app.production_lines.status import line_board
from app.production_orders.routes import bundle_counts, progress_info, resched_data
from app.production_orders.scheduler import live_schedule, today_ist
from app.production_orders.stage_material import later_stage_gaps

production_planning_bp = Blueprint("production_planning", __name__, template_folder="templates")


def draft_split(queue):
    # Queue ke Draft orders: (planning baaki, plan pakka — release ke liye tayyar)
    drafts = [o for o in queue if o.status == "Draft"]
    return [o for o in drafts if not o.plan_confirmed], [o for o in drafts if o.plan_confirmed]


@production_planning_bp.route("/production_planning")
def production_planning_page():
    tab = request.args.get("tab", "needs")
    if tab not in ("needs", "ready", "queue"):
        tab = "needs"
    today = today_ist()
    queue, materials, schedule = live_schedule()
    needs, ready = draft_split(queue)
    # Queue tab: Release ho chuke aur chalte hue orders (queue ke order me)
    running = [o for o in queue if o.status in ("Released", "In production")]
    shown = {"needs": needs, "ready": ready, "queue": running}[tab]
    open_orders = needs + ready + running
    late = len([o for o in open_orders if o.needed_by_date and schedule.get(o.id) and schedule[o.id]["end"] > o.needed_by_date])
    need_material = len([o for o in open_orders if materials.get(o.id, {}).get("status") in ("making", "coming", "buy")])
    progress, stage_now = progress_info(queue, schedule, today)
    return render_template(
        "production_planning.html", active_nav="production_planning", tab=tab, orders=shown, bundles=bundle_counts(), schedule=schedule, materials=materials,
        needs_count=len(needs), ready_count=len(ready), queue_count=len(running), late_count=late, material_count=need_material, today=today,
        progress=progress, stage_now=stage_now,
        # C7: baad ke stage ka maal abhi issue nahi hua to "wait karega" likha aata hai (Released / In production orders)
        issue_gaps={o.id: later_stage_gaps(o) for o in shown if o.status in ("Released", "In production")},
        # Plan / Reschedule drawer ka data aur Start ke liye lines ki live status
        resched=resched_data(shown), line_board=line_board(today),
    )
