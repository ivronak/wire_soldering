# Sales S10 — Profit report page (Sales > Profit). Hisaab app/sales_profit/profit.py me. Roles aane par sirf Owner ko dikhega.
from datetime import date, datetime

from flask import Blueprint, render_template, request

from app.extensions import db
from app.models import Customer
from app.production_orders.scheduler import today_ist
from app.sales_profit.profit import build_profit

sales_profit_bp = Blueprint("sales_profit", __name__, template_folder="templates")


def _read_date(name, default):
    raw = (request.args.get(name) or "").strip()
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date() if raw else default
    except ValueError:
        return default


@sales_profit_bp.route("/sales_profit")
def profit_page():
    today = today_ist()
    fy = date(today.year if today.month >= 4 else today.year - 1, 4, 1)
    date_from, date_to = _read_date("from", fy), _read_date("to", today)
    if date_from > date_to:
        date_from, date_to = date_to, date_from
    customer = db.session.get(Customer, request.args.get("c", type=int) or 0)
    rows, totals = build_profit(date_from, date_to, customer.id if customer is not None else None)
    customers = Customer.query.filter_by(is_deleted=False).order_by(Customer.name).all()
    return render_template("sales_profit.html", active_nav="sales_profit", rows=rows, totals=totals, date_from=date_from, date_to=date_to,
                           customers=customers, customer=customer, today=today)
