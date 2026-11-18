# Sales S4 — Invoices: dispatch hue maal ka Tax Invoice. Tabs: To invoice / Waiting approval (loss) / Invoices / Cancelled.
# Hisaab app/sales_invoices/billing.py me. Challans (app/dispatch) aur Quotation se juda hai.
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import Quotation, SalesInvoice
from app.production_orders.scheduler import today_ist
from app.sales_invoices.billing import BillingError, active_invoices, approve_loss, cancel_invoice, challan_totals, create_invoice, unbilled_challans

sales_invoices_bp = Blueprint("sales_invoices", __name__, template_folder="templates")

TABS = ("todo", "waiting", "done", "cancelled")


def todo_rows():
    # Quotations jinke challan (dispatch) ka bill abhi nahi bana
    rows = []
    for quotation in Quotation.query.filter_by(is_deleted=False).order_by(Quotation.id).all():
        challans = unbilled_challans(quotation)
        if not challans:
            continue
        rows.append({"q": quotation, "challans": challans, "totals": challan_totals(challans), "first": not active_invoices(quotation)})
    return rows


def drawer_data(rows):
    # JS drawer ko har quotation ka: challans (kis line ka kitna), line ka rate / discount / GST / cost, charges
    data = []
    for r in rows:
        q = r["q"]
        challans = []
        for challan in r["challans"]:
            qty = {}
            for cl in challan.lines:
                key = str(cl.quotation_line_id)
                qty[key] = round(qty.get(key, 0) + cl.qty, 4)         # ek challan me ek line ke kai batch ho sakte hain
            challans.append({"id": challan.id, "no": challan.challan_no, "date": challan.challan_date.strftime("%d %b %Y"), "lines": qty})
        lines = []
        for line in q.lines:
            info = r["totals"].get(line)
            lines.append({"line_id": line.id, "product": line.product.name, "code": line.product.code,
                          "unit": line.product.base_unit.code if line.product.base_unit else "",
                          "rate": line.rate, "discount": line.discount_percent or 0, "gst": line.tax_rate.rate_percent if line.tax_rate else 0,
                          "cost": info["cost"] if info else 0})
        charges = [{"name": c.charge.name if c.charge else "Charge", "amount": c.amount, "effect": c.effect} for c in q.charge_lines] if r["first"] else []
        net = sum((-c["amount"] if c["effect"] == "minus" else c["amount"]) for c in charges)
        data.append({"id": q.id, "no": q.quote_no, "customer": q.customer.name, "po": q.customer_po_no or "", "inter": q.is_inter_state,
                     "charges": charges, "charges_net": round(net, 2), "challans": challans, "lines": lines})
    return data


@sales_invoices_bp.route("/invoices")
def invoices_list():
    tab = (request.args.get("tab") or "todo").strip().lower()
    if tab not in TABS:
        tab = "todo"
    todo = todo_rows()
    by_status = {}
    for status, key in (("Waiting approval", "waiting"), ("Posted", "done"), ("Cancelled", "cancelled")):
        by_status[key] = SalesInvoice.query.filter_by(status=status, is_deleted=False).order_by(SalesInvoice.id.desc()).all()
    counts = {"todo": len(todo), "waiting": len(by_status["waiting"]), "done": len(by_status["done"]), "cancelled": len(by_status["cancelled"])}
    return render_template("invoices.html", active_nav="invoices", tab=tab, counts=counts, todo=todo, invoices=by_status.get(tab, []),
                           drawer=drawer_data(todo), today=today_ist().isoformat(), open_q=request.args.get("q", type=int))


@sales_invoices_bp.route("/invoices/add/<int:quotation_id>", methods=["POST"])
def invoices_add(quotation_id):
    quotation = Quotation.query.filter_by(id=quotation_id, is_deleted=False).first_or_404()
    back = redirect(url_for("sales_invoices.invoices_list", q=quotation.id))
    try:
        invoice_date = datetime.strptime((request.form.get("invoice_date") or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        flash("Enter a valid invoice date.", "error")
        return back
    if invoice_date > today_ist():
        flash("The invoice date cannot be in the future.", "error")
        return back
    chosen = {int(x) for x in request.form.getlist("challan_id") if x.isdigit()}
    challans = [c for c in unbilled_challans(quotation) if c.id in chosen]
    if not challans:
        flash("Choose at least one challan to bill.", "error")
        return back
    rates, discounts = {}, {}
    for line in quotation.lines:
        for store, name, label in ((rates, "rate", "rate"), (discounts, "discount", "discount")):
            raw = (request.form.get(f"{name}_{line.id}") or "").strip()
            if not raw:
                continue
            try:
                store[line.id] = float(raw)
            except ValueError:
                flash(f"{line.product.name}: enter a valid {label}.", "error")
                return back
    try:
        invoice = create_invoice(quotation, challans, invoice_date, rates, discounts, remarks=(request.form.get("remarks") or "").strip()[:255] or None)
    except BillingError as error:
        db.session.rollback()
        flash(str(error), "error")
        return back
    db.session.commit()
    if invoice.status == "Waiting approval":
        flash(f"Invoice {invoice.invoice_no} is saved but NOT posted: the rate is below cost (loss ₹{invoice.loss_amount:,.2f}). The Owner must approve it first.", "error")
        return redirect(url_for("sales_invoices.invoices_list", tab="waiting"))
    flash(f"Invoice {invoice.invoice_no} created for {quotation.quote_no}. Total ₹{invoice.total_amount:,.2f}.", "success")
    return redirect(url_for("sales_invoices.invoices_list", tab="done"))


@sales_invoices_bp.route("/invoices/<int:invoice_id>/approve", methods=["POST"])
def invoices_approve(invoice_id):
    invoice = SalesInvoice.query.filter_by(id=invoice_id, is_deleted=False).first_or_404()
    back = redirect(url_for("sales_invoices.invoices_list", tab="waiting"))
    note = (request.form.get("note") or "").strip()[:255]
    if len(note) < 3:
        flash("Write why this loss is accepted.", "error")
        return back
    try:
        approve_loss(invoice, note)
    except BillingError as error:
        flash(str(error), "error")
        return back
    db.session.commit()
    flash(f"Invoice {invoice.invoice_no} approved by the Owner and posted. Total ₹{invoice.total_amount:,.2f}.", "success")
    return redirect(url_for("sales_invoices.invoices_list", tab="done"))


@sales_invoices_bp.route("/invoices/<int:invoice_id>/cancel", methods=["POST"])
def invoices_cancel(invoice_id):
    invoice = SalesInvoice.query.filter_by(id=invoice_id, is_deleted=False).first_or_404()
    back = redirect(url_for("sales_invoices.invoices_list", tab="done"))
    reason = (request.form.get("reason") or "").strip()[:255]
    if len(reason) < 3:
        flash("Write why the invoice is cancelled.", "error")
        return back
    try:
        cancel_invoice(invoice, reason)
    except BillingError as error:
        flash(str(error), "error")
        return back
    db.session.commit()
    flash(f"Invoice {invoice.invoice_no} cancelled. Its challans can be billed again.", "success")
    return redirect(url_for("sales_invoices.invoices_list", tab="cancelled"))


@sales_invoices_bp.route("/invoices/<int:invoice_id>/print")
def invoices_print(invoice_id):
    invoice = SalesInvoice.query.filter_by(id=invoice_id, is_deleted=False).first_or_404()
    if invoice.status != "Posted":
        # Loss wala (Waiting approval) invoice Owner ke approve se pehle customer ko nahi jaana chahiye
        flash("Only a posted invoice can be printed. A waiting invoice needs the Owner's approval first.", "error")
        return redirect(url_for("sales_invoices.invoices_list", tab="waiting" if invoice.status == "Waiting approval" else "cancelled"))
    return render_template("invoice_print.html", inv=invoice, q=invoice.quotation, summary=invoice.summary)
