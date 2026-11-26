# Accounts A6 — Ledger statement: kisi bhi ledger ke voucher entries, opening + running balance + closing (Tally ke Ledger Vouchers jaisa).
# Sirf voucher_entries se banta hai (Ledger.current_balance se nahi). Balance Dr / Cr me dikhate hain: Dr - Cr plus ho to "Dr", minus ho to "Cr".
from datetime import date, datetime

from flask import Blueprint, render_template, request

from app.accounts.manual import pickable_ledgers
from app.accounts.posting import paise
from app.extensions import db
from app.models import Ledger, Voucher, VoucherEntry
from app.production_orders.scheduler import today_ist

ledger_statement_bp = Blueprint("ledger_statement", __name__, template_folder="templates")


def fy_start(today):
    # Financial year April-March (flow doc decision)
    return date(today.year if today.month >= 4 else today.year - 1, 4, 1)


def _signed(entries):
    # Dr - Cr, paise me (integer)
    return sum(paise(e.amount) if e.side == "Dr" else -paise(e.amount) for e in entries)


def build_statement(ledger, date_from, date_to):
    """(opening_dr_minus_cr, rows, closing) — sab paise me nahi, rupees me. Row = dict(voucher, entry, dr, cr, running)."""
    base = (db.session.query(VoucherEntry).join(Voucher, Voucher.id == VoucherEntry.voucher_id).filter(VoucherEntry.ledger_id == ledger.id))
    opening = _signed(base.filter(Voucher.voucher_date < date_from).all())
    entries = (base.filter(Voucher.voucher_date >= date_from, Voucher.voucher_date <= date_to)
               .order_by(Voucher.voucher_date, Voucher.id, VoucherEntry.id).all())
    rows, running, dr_total, cr_total = [], opening, 0, 0
    for entry in entries:
        cents = paise(entry.amount)
        dr, cr = (cents, 0) if entry.side == "Dr" else (0, cents)
        running += dr - cr
        dr_total += dr
        cr_total += cr
        rows.append({"voucher": entry.voucher, "entry": entry, "dr": dr / 100, "cr": cr / 100, "running": running / 100})
    return opening / 100, rows, running / 100, dr_total / 100, cr_total / 100


def dr_cr_text(value):
    # +ve = Dr, -ve = Cr
    if abs(value) < 0.005:
        return "0.00"
    return "{:,.2f} {}".format(abs(value), "Dr" if value > 0 else "Cr")


@ledger_statement_bp.route("/ledger_statement")
def statement_page():
    today = today_ist()
    ledger = db.session.get(Ledger, request.args.get("ledger", type=int) or 0)
    try:
        date_from = datetime.strptime((request.args.get("from") or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        date_from = fy_start(today)
    try:
        date_to = datetime.strptime((request.args.get("to") or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        date_to = today
    data = build_statement(ledger, date_from, date_to) if ledger else None
    ledgers = [{"id": l.id, "name": l.name, "group": l.group.name} for l in pickable_ledgers()]
    return render_template("ledger_statement.html", active_nav="ledger_statement", ledger=ledger, ledgers=ledgers, date_from=date_from, date_to=date_to,
                           data=data, dr_cr=dr_cr_text)
