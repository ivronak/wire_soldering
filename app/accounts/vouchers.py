# Accounts A6 — Vouchers: list (filter), View, naya manual voucher (Payment / Receipt / Journal / Contra), reverse.
# Posting logic app/accounts/manual.py + posting.py me. Auto-posting wale voucher yahan sirf dikhte hain.
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.accounts.manual import MANUAL_TYPES, pickable_ledgers, post_manual, reverse_manual
from app.accounts.posting import VOUCHER_TYPES, VoucherError
from app.auth import service as auth_service
from app.extensions import db
from app.models import Ledger, ProductionOutput, PurchaseInvoice, PurchaseReturn, SalesInvoice, SalesReceipt, SalesReturn, Voucher, VendorPayment
from app.production_orders.scheduler import today_ist

vouchers_bp = Blueprint("vouchers", __name__, template_folder="templates")

SOURCE_LABELS = {"sales_invoice": ("Sales invoice", SalesInvoice, "invoice_no"), "sales_receipt": ("Receipt", SalesReceipt, "receipt_no"),
                 "sales_return": ("Credit note", SalesReturn, "return_no"), "purchase_invoice": ("Purchase bill", PurchaseInvoice, "pi_no"),
                 "purchase_return": ("Purchase return", PurchaseReturn, "pr_no"), "vendor_payment": ("Vendor payment", VendorPayment, "payment_no"),
                 "ledger_opening": ("Opening balance", Ledger, "name"), "manual": ("Manual entry", None, None),
                 "production_fixed_cost": ("Production output", ProductionOutput, "output_no")}


def source_text(voucher):
    # "Sales invoice INV-2026-001" jaisa chhota text; document na mile to sirf type
    label, model, attr = SOURCE_LABELS.get(voucher.source_type, (voucher.source_type or "", None, None))
    if model is not None and voucher.source_id:
        row = db.session.get(model, voucher.source_id)
        if row is not None:
            return f"{label} {getattr(row, attr)}"
    return label


def _date_arg(name):
    try:
        return datetime.strptime((request.args.get(name) or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


@vouchers_bp.route("/vouchers")
def vouchers_list():
    vtype = (request.args.get("type") or "").strip()
    date_from, date_to = _date_arg("from"), _date_arg("to")
    q = (request.args.get("q") or "").strip()
    query = Voucher.query
    if vtype in VOUCHER_TYPES:
        query = query.filter(Voucher.voucher_type == vtype)
    if date_from:
        query = query.filter(Voucher.voucher_date >= date_from)
    if date_to:
        query = query.filter(Voucher.voucher_date <= date_to)
    if q:
        query = query.filter(db.or_(Voucher.voucher_no.ilike(f"%{q}%"), Voucher.narration.ilike(f"%{q}%")))
    total = query.count()
    rows = query.order_by(Voucher.voucher_date.desc(), Voucher.id.desc()).limit(300).all()
    return render_template("vouchers.html", active_nav="vouchers", rows=rows, total=total, vtype=vtype, q=q, date_from=date_from, date_to=date_to,
                           types=list(VOUCHER_TYPES), source_text=source_text)


@vouchers_bp.route("/vouchers/<int:voucher_id>")
def voucher_view(voucher_id):
    voucher = db.get_or_404(Voucher, voucher_id)
    return render_template("voucher_view.html", active_nav="vouchers", v=voucher, source=source_text(voucher))


@vouchers_bp.route("/vouchers/new")
def voucher_new():
    vtype = request.args.get("type") if request.args.get("type") in MANUAL_TYPES else "Payment"
    ledgers = [{"id": l.id, "name": l.name, "group": l.group.name} for l in pickable_ledgers()]
    return render_template("voucher_new.html", active_nav="vouchers", vtype=vtype, types=MANUAL_TYPES, ledgers=ledgers, today=today_ist().isoformat(),
                           form=None)


@vouchers_bp.route("/vouchers/add", methods=["POST"])
def voucher_add():
    vtype = request.form.get("voucher_type")
    back = redirect(url_for("vouchers.voucher_new", type=vtype))
    try:
        vdate = datetime.strptime((request.form.get("voucher_date") or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        flash("Enter a valid voucher date.", "error")
        return back
    if vdate > today_ist():
        flash("The voucher date cannot be in the future.", "error")
        return back
    lines = []
    try:
        for n in range(request.form.get("line_count", type=int) or 0):
            ledger_id = request.form.get(f"ledger_{n}", type=int)
            raw = (request.form.get(f"amount_{n}") or "").strip()
            if not ledger_id and not raw:
                continue            # khaali line chhod do
            side = request.form.get(f"side_{n}")
            ledger = db.session.get(Ledger, ledger_id or 0)
            if ledger is None or not raw:
                raise VoucherError("Each line needs a ledger and an amount.")
            lines.append((ledger, side, float(raw)))
        narration = (request.form.get("narration") or "").strip()[:255] or None
        voucher = post_manual(vtype, vdate, lines, narration, created_by_id=auth_service.actor_id())
    except ValueError as error:         # VoucherError bhi ValueError hai; float() galat ho to bhi yahi
        db.session.rollback()
        flash(str(error) if isinstance(error, VoucherError) else "Enter valid amounts.", "error")
        return back
    db.session.commit()
    flash(f"Voucher {voucher.voucher_no} posted.", "success")
    return redirect(url_for("vouchers.voucher_view", voucher_id=voucher.id))


@vouchers_bp.route("/vouchers/<int:voucher_id>/reverse", methods=["POST"])
def voucher_reverse(voucher_id):
    voucher = db.get_or_404(Voucher, voucher_id)
    back = redirect(url_for("vouchers.voucher_view", voucher_id=voucher.id))
    try:
        reversal = reverse_manual(voucher, request.form.get("reason"), created_by_id=auth_service.actor_id())
    except VoucherError as error:
        db.session.rollback()
        flash(str(error), "error")
        return back
    db.session.commit()
    flash(f"Voucher {voucher.voucher_no} reversed by {reversal.voucher_no}.", "success")
    return back
