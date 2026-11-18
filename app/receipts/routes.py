# Sales S5 — Receipts: customer se mila paisa. Tabs: To collect (kis customer se kitna lena baaki) / Receipts / Cancelled.
# Hisaab app/receipts/collect.py me. Sales Invoices (outstanding) aur customers.ledger se juda hai.
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import Customer, PaymentMode, SalesInvoice, SalesReceipt
from app.production_orders.scheduler import today_ist
from app.receipts.collect import ReceiptError, allocate_more, cancel_receipt, create_receipt, on_account_total, open_invoices

receipts_bp = Blueprint("receipts", __name__, template_folder="templates")

TABS = ("todo", "done", "cancelled")


def _invoice_row(invoice):
    return {"id": invoice.id, "no": invoice.invoice_no, "date": invoice.invoice_date.strftime("%d %b %Y"), "total": invoice.total_amount,
            "paid": invoice.paid, "due": invoice.outstanding}


def customer_rows():
    # Har customer: ledger balance (minus = lena), baaki invoices, advance (On account). Receipt form (JS) isi se chalta hai
    rows = []
    for customer in Customer.query.filter_by(is_deleted=False).order_by(Customer.name).all():
        invoices = open_invoices(customer)
        rows.append({"id": customer.id, "name": customer.name, "balance": customer.ledger.current_balance if customer.ledger else 0,
                     "invoices": [_invoice_row(i) for i in invoices], "due": round(sum(i.outstanding for i in invoices), 2),
                     "advance": on_account_total(customer)})
    return rows


@receipts_bp.route("/receipts")
def receipts_list():
    tab = (request.args.get("tab") or "todo").strip().lower()
    if tab not in TABS:
        tab = "todo"
    all_rows = customer_rows()
    todo = [r for r in all_rows if r["due"] > 0.004]
    done = SalesReceipt.query.filter_by(status="Posted", is_deleted=False).order_by(SalesReceipt.id.desc()).all()
    cancelled = SalesReceipt.query.filter_by(status="Cancelled", is_deleted=False).order_by(SalesReceipt.id.desc()).all()
    counts = {"todo": len(todo), "done": len(done), "cancelled": len(cancelled)}
    modes = PaymentMode.query.filter_by(is_deleted=False, is_active=True).order_by(PaymentMode.id).all()
    return render_template("receipts.html", active_nav="receipts", tab=tab, counts=counts, todo=todo, receipts=done if tab == "done" else cancelled,
                           customers=all_rows, modes=modes, today=today_ist().isoformat(), open_customer=request.args.get("c", type=int),
                           total_due=round(sum(r["due"] for r in todo), 2),
                           alloc_data={r.id: {"no": r.receipt_no, "customer": r.customer.name, "left": r.on_account,
                                              "invoices": [_invoice_row(i) for i in open_invoices(r.customer)]} for r in done if r.on_account > 0.004})


def _read_alloc():
    # alloc_<invoice_id> = amount (khaali = 0). Galat likha ho to ReceiptError
    alloc = {}
    for key, raw in request.form.items():
        if not key.startswith("alloc_"):
            continue
        raw = (raw or "").strip()
        if not raw:
            continue
        try:
            alloc[int(key[6:])] = float(raw)
        except ValueError:
            raise ReceiptError("Enter valid amounts against the invoices.")
    return alloc


@receipts_bp.route("/receipts/add", methods=["POST"])
def receipts_add():
    back = redirect(url_for("receipts.receipts_list"))
    customer = db.session.get(Customer, request.form.get("customer_id", type=int) or 0)
    if customer is None or customer.is_deleted:
        flash("Choose a customer.", "error")
        return back
    back = redirect(url_for("receipts.receipts_list", c=customer.id))
    try:
        receipt_date = datetime.strptime((request.form.get("receipt_date") or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        flash("Enter a valid receipt date.", "error")
        return back
    if receipt_date > today_ist():
        flash("The receipt date cannot be in the future.", "error")
        return back
    try:
        amount = float((request.form.get("amount") or "").strip())
    except ValueError:
        flash("Enter a valid amount.", "error")
        return back
    mode = db.session.get(PaymentMode, request.form.get("payment_mode_id", type=int) or 0)
    try:
        receipt = create_receipt(customer, receipt_date, amount, mode, (request.form.get("reference") or "").strip()[:60] or None,
                                 (request.form.get("notes") or "").strip()[:255] or None, _read_alloc())
    except ReceiptError as error:
        db.session.rollback()
        flash(str(error), "error")
        return back
    db.session.commit()
    extra = f" ₹{receipt.on_account:,.2f} is kept on account." if receipt.on_account > 0.004 else ""
    flash(f"Receipt {receipt.receipt_no} saved: ₹{receipt.amount:,.2f} from {customer.name}.{extra}", "success")
    return redirect(url_for("receipts.receipts_list", tab="done"))


@receipts_bp.route("/receipts/<int:receipt_id>/allocate", methods=["POST"])
def receipts_allocate(receipt_id):
    receipt = SalesReceipt.query.filter_by(id=receipt_id, is_deleted=False).first_or_404()
    back = redirect(url_for("receipts.receipts_list", tab="done"))
    try:
        allocate_more(receipt, _read_alloc())
    except ReceiptError as error:
        db.session.rollback()
        flash(str(error), "error")
        return back
    db.session.commit()
    flash(f"Receipt {receipt.receipt_no}: money on account applied to the invoices. ₹{receipt.on_account:,.2f} is still on account.", "success")
    return back


@receipts_bp.route("/receipts/<int:receipt_id>/cancel", methods=["POST"])
def receipts_cancel(receipt_id):
    receipt = SalesReceipt.query.filter_by(id=receipt_id, is_deleted=False).first_or_404()
    back = redirect(url_for("receipts.receipts_list", tab="done"))
    reason = (request.form.get("reason") or "").strip()[:255]
    if len(reason) < 3:
        flash("Write why the receipt is cancelled.", "error")
        return back
    try:
        cancel_receipt(receipt, reason)
    except ReceiptError as error:
        flash(str(error), "error")
        return back
    db.session.commit()
    flash(f"Receipt {receipt.receipt_no} cancelled. The customer's dues are back.", "success")
    return redirect(url_for("receipts.receipts_list", tab="cancelled"))
