# Sales S7 — Sales returns (Credit notes): customer ne jo maal wapas bheja. Tabs: Credit notes / Cancelled.
# Hisaab app/sales_returns/returns.py me. Sales Invoices, FG stock (batch) aur customers.ledger se juda hai.
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import SalesInvoice, SalesReturn
from app.production_orders.scheduler import today_ist
from app.sales_returns.returns import ReturnError, cancel_return, create_return, returnable_invoices, returnable_qty, returned_qty

sales_returns_bp = Blueprint("sales_returns", __name__, template_folder="templates")

TABS = ("done", "cancelled")


def invoice_rows():
    # Return form (JS) ke liye: har returnable invoice, uski lines, kitna wapas aa chuka, kitna baaki, wapas ka bhaav (discount ke baad)
    rows = []
    for inv in returnable_invoices():
        lines = []
        for line in inv.lines:
            left = returnable_qty(line)
            if left <= 0.00005:
                continue
            lines.append({"id": line.id, "product": line.product.name, "code": line.product.code, "unit": line.product.base_unit.code if line.product.base_unit else "",
                          "qty": line.qty, "returned": returned_qty(line), "left": left, "net_unit": line.net_unit_price,
                          "gst": line.tax_rate.rate_percent if line.tax_rate else 0})
        rows.append({"id": inv.id, "no": inv.invoice_no, "customer": inv.quotation.customer.name, "date": inv.invoice_date.strftime("%d %b %Y"),
                     "date_iso": inv.invoice_date.isoformat(), "inter": inv.is_inter_state, "lines": lines})
    return rows


@sales_returns_bp.route("/sales_returns")
def returns_list():
    tab = (request.args.get("tab") or "done").strip().lower()
    if tab not in TABS:
        tab = "done"
    done = SalesReturn.query.filter_by(status="Posted", is_deleted=False).order_by(SalesReturn.id.desc()).all()
    cancelled = SalesReturn.query.filter_by(status="Cancelled", is_deleted=False).order_by(SalesReturn.id.desc()).all()
    return render_template("sales_returns.html", active_nav="sales_returns", tab=tab, counts={"done": len(done), "cancelled": len(cancelled)},
                           returns=done if tab == "done" else cancelled, invoices=invoice_rows(), today=today_ist().isoformat(),
                           open_invoice=request.args.get("i", type=int))


def _num(raw):
    raw = (raw or "").strip()
    return float(raw) if raw else 0.0


@sales_returns_bp.route("/sales_returns/add", methods=["POST"])
def returns_add():
    back = redirect(url_for("sales_returns.returns_list"))
    invoice = db.session.get(SalesInvoice, request.form.get("invoice_id", type=int) or 0)
    if invoice is None or invoice.is_deleted:
        flash("Choose an invoice.", "error")
        return back
    back = redirect(url_for("sales_returns.returns_list", i=invoice.id))
    try:
        return_date = datetime.strptime((request.form.get("return_date") or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        flash("Enter a valid return date.", "error")
        return back
    if return_date > today_ist():
        flash("The return date cannot be in the future.", "error")
        return back
    wanted = {}
    try:
        for line in invoice.lines:
            wanted[line.id] = (_num(request.form.get(f"qty_{line.id}")), _num(request.form.get(f"damaged_{line.id}")))
    except ValueError:
        flash("Enter valid quantities.", "error")
        return back
    outstanding_before = invoice.outstanding
    try:
        ret = create_return(invoice, return_date, request.form.get("reason"), wanted)
    except ReturnError as error:
        db.session.rollback()
        flash(str(error), "error")
        return back
    db.session.commit()
    message = f"Credit note {ret.return_no} saved: ₹{ret.total_amount:,.2f} credited to {ret.customer.name}."
    extra = round(ret.total_amount - outstanding_before, 2)
    if extra > 0.004:
        message += f" The invoice was already paid up, so ₹{extra:,.2f} stays as credit with the customer."
    flash(message, "success")
    return redirect(url_for("sales_returns.returns_list"))


@sales_returns_bp.route("/sales_returns/<int:return_id>/cancel", methods=["POST"])
def returns_cancel(return_id):
    ret = SalesReturn.query.filter_by(id=return_id, is_deleted=False).first_or_404()
    back = redirect(url_for("sales_returns.returns_list"))
    reason = (request.form.get("reason") or "").strip()[:255]
    if len(reason) < 3:
        flash("Write why the credit note is cancelled.", "error")
        return back
    try:
        cancel_return(ret, reason)
    except ReturnError as error:
        db.session.rollback()
        flash(str(error), "error")
        return back
    db.session.commit()
    flash(f"Credit note {ret.return_no} cancelled. The customer account and stock are back as before.", "success")
    return redirect(url_for("sales_returns.returns_list", tab="cancelled"))


@sales_returns_bp.route("/sales_returns/<int:return_id>/print")
def returns_print(return_id):
    ret = SalesReturn.query.filter_by(id=return_id, is_deleted=False).first_or_404()
    invoice = ret.invoice
    return render_template("credit_note_print.html", ret=ret, inv=invoice, q=invoice.quotation, summary=ret.summary)
