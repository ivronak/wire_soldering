# Sales S8 — Customer statement page + A4 print (Sales > Customer statement). Hisaab app/customer_statement/statement.py me.
from datetime import date, datetime

from flask import Blueprint, render_template, request

from app.customer_statement.statement import build_statement
from app.extensions import db
from app.models import Customer
from app.production_orders.scheduler import today_ist

customer_statement_bp = Blueprint("customer_statement", __name__, template_folder="templates")


def _fy_start(today):
    # Financial year 1 April se (India)
    return date(today.year if today.month >= 4 else today.year - 1, 4, 1)


def _read_date(name, default):
    raw = (request.args.get(name) or "").strip()
    if not raw:
        return default
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return default


def _context():
    today = today_ist()
    date_from = _read_date("from", _fy_start(today))
    date_to = _read_date("to", today)
    if date_from > date_to:
        date_from, date_to = date_to, date_from
    customers = Customer.query.filter_by(is_deleted=False).order_by(Customer.name).all()
    customer = db.session.get(Customer, request.args.get("c", type=int) or 0)
    if customer is not None and customer.is_deleted:
        customer = None
    data = build_statement(customer, date_from, date_to) if customer is not None else None
    return {"customers": customers, "customer": customer, "data": data, "date_from": date_from, "date_to": date_to, "today": today}


@customer_statement_bp.route("/customer_statement")
def statement_page():
    return render_template("customer_statement.html", active_nav="statement", **_context())


@customer_statement_bp.route("/customer_statement/print")
def statement_print():
    ctx = _context()
    if ctx["customer"] is None:
        return render_template("customer_statement.html", active_nav="statement", **ctx)
    return render_template("statement_print.html", **ctx)
