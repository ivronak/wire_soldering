# Accounts A5 — Payables aging page (Accounts > Payables). Hisaab app/payables/aging.py me.
from datetime import datetime

from flask import Blueprint, render_template, request

from app.payables.aging import BUCKET_LABELS, BUCKETS, build_payables
from app.production_orders.scheduler import today_ist

payables_bp = Blueprint("payables", __name__, template_folder="templates")


@payables_bp.route("/payables")
def payables_aging():
    today = today_ist()
    as_on = today
    raw = (request.args.get("as_on") or "").strip()
    if raw:
        try:
            as_on = datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            as_on = today
    rows, totals = build_payables(as_on)
    overdue = round(totals["b1"] + totals["b2"] + totals["b3"] + totals["b4"], 2)
    return render_template("payables_aging.html", active_nav="payables", rows=rows, totals=totals, overdue=overdue, as_on=as_on,
                           today=today, buckets=BUCKETS, labels=BUCKET_LABELS)
