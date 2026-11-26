# Accounts A5 — Vendor payments: To pay (kis vendor ko kitna dena baaki) / Payments / Cancelled + naya payment (bill-by-bill).
# Hisaab app/vendor_payments/collect.py me. Purchase invoices (outstanding) aur vendors.ledger se juda hai.
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import PaymentMode, Vendor, VendorPayment
from app.production_orders.scheduler import today_ist
from app.vendor_payments.collect import PaymentError, allocate_more, cancel_payment, create_payment, on_account_total, open_bills

vendor_payments_bp = Blueprint("vendor_payments", __name__, template_folder="templates")

TABS = ("todo", "done", "cancelled")


def vendor_rows():
    rows = []
    for vendor in Vendor.query.filter_by(is_deleted=False).order_by(Vendor.name).all():
        bills = open_bills(vendor)
        rows.append({"id": vendor.id, "name": vendor.name, "balance": vendor.ledger.current_balance if vendor.ledger else 0,
                     "bills": bills, "due": round(sum(b.outstanding for b in bills), 2), "advance": on_account_total(vendor)})
    return rows


@vendor_payments_bp.route("/vendor_payments")
def payments_list():
    tab = (request.args.get("tab") or "todo").strip().lower()
    if tab not in TABS:
        tab = "todo"
    todo = [r for r in vendor_rows() if r["due"] > 0.004]
    done = VendorPayment.query.filter_by(status="Posted", is_deleted=False).order_by(VendorPayment.id.desc()).all()
    cancelled = VendorPayment.query.filter_by(status="Cancelled", is_deleted=False).order_by(VendorPayment.id.desc()).all()
    counts = {"todo": len(todo), "done": len(done), "cancelled": len(cancelled)}
    return render_template("vendor_payments.html", active_nav="vendor_payments", tab=tab, counts=counts, todo=todo,
                           payments=done if tab == "done" else cancelled, total_due=round(sum(r["due"] for r in todo), 2))


@vendor_payments_bp.route("/vendor_payments/new")
def payments_new():
    # Vendor chuno -> uske baaki bills dikhte hain, har bill ke saamne kitna de rahe ho likho
    vendor = db.session.get(Vendor, request.args.get("v", type=int) or 0)
    if vendor is not None and vendor.is_deleted:
        vendor = None
    modes = PaymentMode.query.filter_by(is_deleted=False, is_active=True).order_by(PaymentMode.id).all()
    vendors = Vendor.query.filter_by(is_deleted=False).order_by(Vendor.name).all()
    return render_template("vendor_payment_new.html", active_nav="vendor_payments", vendor=vendor, vendors=vendors, modes=modes,
                           bills=open_bills(vendor) if vendor else [], advance=on_account_total(vendor) if vendor else 0,
                           balance=vendor.ledger.current_balance if vendor and vendor.ledger else 0, today=today_ist().isoformat())


def _read_alloc():
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
            raise PaymentError("Enter valid amounts against the bills.")
    return alloc


@vendor_payments_bp.route("/vendor_payments/add", methods=["POST"])
def payments_add():
    vendor = db.session.get(Vendor, request.form.get("vendor_id", type=int) or 0)
    if vendor is None or vendor.is_deleted:
        flash("Choose a vendor.", "error")
        return redirect(url_for("vendor_payments.payments_new"))
    back = redirect(url_for("vendor_payments.payments_new", v=vendor.id))
    try:
        payment_date = datetime.strptime((request.form.get("payment_date") or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        flash("Enter a valid payment date.", "error")
        return back
    if payment_date > today_ist():
        flash("The payment date cannot be in the future.", "error")
        return back
    try:
        amount = float((request.form.get("amount") or "").strip())
    except ValueError:
        flash("Enter a valid amount.", "error")
        return back
    mode = db.session.get(PaymentMode, request.form.get("payment_mode_id", type=int) or 0)
    try:
        payment = create_payment(vendor, payment_date, amount, mode, (request.form.get("reference") or "").strip()[:60] or None,
                                 (request.form.get("notes") or "").strip()[:255] or None, _read_alloc())
    except Exception as error:      # PaymentError ya VoucherError — kuch save nahi hoga, message seedha user ko
        db.session.rollback()
        flash(str(error), "error")
        return back
    db.session.commit()
    extra = f" ₹{payment.on_account:,.2f} is kept on account." if payment.on_account > 0.004 else ""
    flash(f"Payment {payment.payment_no} saved: ₹{payment.amount:,.2f} to {vendor.name}.{extra}", "success")
    return redirect(url_for("vendor_payments.payments_list", tab="done"))


@vendor_payments_bp.route("/vendor_payments/<int:payment_id>/cancel", methods=["POST"])
def payments_cancel(payment_id):
    payment = VendorPayment.query.filter_by(id=payment_id, is_deleted=False).first_or_404()
    back = redirect(url_for("vendor_payments.payments_list", tab="done"))
    reason = (request.form.get("reason") or "").strip()[:255]
    if len(reason) < 3:
        flash("Write why the payment is cancelled.", "error")
        return back
    try:
        cancel_payment(payment, reason)
    except Exception as error:
        db.session.rollback()
        flash(str(error), "error")
        return back
    db.session.commit()
    flash(f"Payment {payment.payment_no} cancelled. The bills are due again.", "success")
    return redirect(url_for("vendor_payments.payments_list", tab="cancelled"))


@vendor_payments_bp.route("/vendor_payments/<int:payment_id>/apply", methods=["GET", "POST"])
def payments_apply(payment_id):
    # On account (advance) paisa ko ab vendor ke baaki bills ke against lagao
    payment = VendorPayment.query.filter_by(id=payment_id, is_deleted=False).first_or_404()
    if payment.status != "Posted" or payment.on_account <= 0.004:
        flash("This payment has no money on account.", "error")
        return redirect(url_for("vendor_payments.payments_list", tab="done"))
    if request.method == "POST":
        try:
            allocate_more(payment, _read_alloc())
        except Exception as error:
            db.session.rollback()
            flash(str(error), "error")
            return redirect(url_for("vendor_payments.payments_apply", payment_id=payment.id))
        db.session.commit()
        flash(f"Payment {payment.payment_no}: money on account applied to the bills. ₹{payment.on_account:,.2f} is still on account.", "success")
        return redirect(url_for("vendor_payments.payments_list", tab="done"))
    return render_template("vendor_payment_apply.html", active_nav="vendor_payments", p=payment, bills=open_bills(payment.vendor))
