# Sales S6 — Receivables aging page (Sales > Receivables). Hisaab app/aging/aging.py me.
from datetime import datetime

from flask import Blueprint, render_template, request

from app.aging.aging import BUCKET_LABELS, BUCKETS, build_aging
from app.production_orders.scheduler import today_ist

aging_bp = Blueprint("aging", __name__, template_folder="templates")


@aging_bp.route("/receivables")
def receivables_aging():
    today = today_ist()
    # As-on date: default aaj. Aage ki date daal kar dekh sakte ho ki tab tak kitna late ho jayega (paisa wahi jo abhi baaki hai)
    as_on = today
    raw = (request.args.get("as_on") or "").strip()
    if raw:
        try:
            as_on = datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            as_on = today
    rows, totals = build_aging(as_on)
    overdue = round(totals["b1"] + totals["b2"] + totals["b3"] + totals["b4"], 2)
    return render_template("receivables_aging.html", active_nav="aging", rows=rows, totals=totals, overdue=overdue, as_on=as_on,
                           today=today, buckets=BUCKETS, labels=BUCKET_LABELS)
