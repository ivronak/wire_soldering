# Accounts A7 — Reports (key accounts_reports, profit jaisa sensitive isliye alag role key): Day book, Cash / Bank book, Trial Balance, P&L, Balance Sheet.
# Hisaab app/accounts/reports.py me; Cash / Bank book app/accounts/statement.py ka build_statement dobara use karta hai.
from datetime import datetime

from flask import Blueprint, render_template, request

from app.accounts import reports as rpt
from app.accounts.manual import is_cash_bank
from app.accounts.statement import build_statement, dr_cr_text, fy_start
from app.extensions import db
from app.models import Ledger
from app.production_orders.scheduler import today_ist

reports_bp = Blueprint("reports", __name__, template_folder="templates")


def _date(name, default):
    try:
        return datetime.strptime((request.args.get(name) or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        return default


@reports_bp.route("/accounts/reports")
def reports_index():
    return render_template("report_index.html", active_nav="accounts_reports")


@reports_bp.route("/accounts/reports/daybook")
def daybook():
    today = today_ist()
    date_from, date_to = _date("from", today), _date("to", today)
    vouchers, total = rpt.day_book(date_from, date_to)
    return render_template("report_daybook.html", active_nav="accounts_reports", vouchers=vouchers, total=total, date_from=date_from, date_to=date_to)


@reports_bp.route("/accounts/reports/cashbook")
def cashbook():
    # Cash book + Bank book ek page par: sirf Cash-in-hand / Bank Accounts group ke ledger chunne ko
    today = today_ist()
    date_from, date_to = _date("from", fy_start(today)), _date("to", today)
    options = [l for l in Ledger.query.filter_by(is_active=True).all() if is_cash_bank(l)]
    options.sort(key=lambda l: (l.group.name, l.name))
    ledger = db.session.get(Ledger, request.args.get("ledger", type=int) or 0)
    if ledger is not None and not is_cash_bank(ledger):
        ledger = None
    if ledger is None and options and not request.args.get("ledger"):
        ledger = options[0]
    data = build_statement(ledger, date_from, date_to) if ledger else None
    return render_template("ledger_statement.html", active_nav="accounts_reports", ledger=ledger, date_from=date_from, date_to=date_to, data=data, dr_cr=dr_cr_text,
                           ledgers=[{"id": l.id, "name": l.name, "group": l.group.name} for l in options], page_title="Cash / Bank book",
                           page_sub="Cash and bank ledgers only, with a running balance", crumb="Accounts / Reports / Cash & bank book")


@reports_bp.route("/accounts/reports/trial_balance")
def trial_balance():
    as_on = _date("as_on", today_ist())
    groups, total_dr, total_cr = rpt.trial_balance(as_on)
    return render_template("report_trial_balance.html", active_nav="accounts_reports", groups=groups, total_dr=total_dr, total_cr=total_cr, as_on=as_on, money=rpt.money)


@reports_bp.route("/accounts/reports/profit_loss")
def profit_loss():
    today = today_ist()
    date_from, date_to = _date("from", fy_start(today)), _date("to", today)
    return render_template("report_profit_loss.html", active_nav="accounts_reports", pl=rpt.profit_loss(date_from, date_to), date_from=date_from, date_to=date_to, money=rpt.money)


@reports_bp.route("/accounts/reports/balance_sheet")
def balance_sheet():
    as_on = _date("as_on", today_ist())
    return render_template("report_balance_sheet.html", active_nav="accounts_reports", bs=rpt.balance_sheet(as_on), as_on=as_on, money=rpt.money)
