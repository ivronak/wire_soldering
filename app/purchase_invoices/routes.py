from datetime import date, datetime

from flask import render_template, Blueprint, request, redirect, url_for, flash
from app.extensions import db
from app.models import (
    PurchaseInvoice, PurchaseInvoiceLine, PurchaseInvoiceCharge,
    GRNLine, Vendor, TaxRate, Charge,
)
from app.purchase_invoices.posting import post_invoice, cancel_invoice

purchase_invoices_bp = Blueprint("purchase_invoices", __name__, template_folder="templates")


def list_url(tab="pending"):
    return url_for("purchase_invoices.purchase_invoices_list", tab=tab)


@purchase_invoices_bp.route("/purchase_invoices")
def purchase_invoices_list():
    # Auto-flow: "New invoice" button nahi. Bill ka kaam pichle step (QC) se khud yahan aata hai.
    #   pending   = (1) QC me pass hue lots jinka bill baaki hai, (2) Draft bills (post baaki)
    #   completed = Posted / Cancelled bills
    tab = (request.args.get("tab") or "pending").strip().lower()
    if tab != "completed":
        tab = "pending"   # ?tab=kuchbhi aaye to bhi pending

    # Saare lots uthao, phir ek-ek ko dekho
    all_lines = GRNLine.query.order_by(GRNLine.id.desc()).all()

    lots = []                          # abhi khaali dabba: isme wahi lots aayenge jinka bill baaki hai
    for gl in all_lines:               # ek-ek lot uthao
        if gl.grn.is_deleted:          # jis GRN ko remove kar diya, uska lot chhod do
            continue                   # "continue" = is lot ko chhodo, agle par jao
        if gl.billable_qty > 0:        # bill ho sakne wali quantity bachi hai
            lots.append(gl)            # to list me daalo

    base = PurchaseInvoice.query.filter(PurchaseInvoice.is_deleted == False)
    draft_invoices = base.filter(PurchaseInvoice.status == "Draft").order_by(PurchaseInvoice.id.desc()).all()
    invoices = base.filter(PurchaseInvoice.status != "Draft").order_by(PurchaseInvoice.id.desc()).all()

    pending_count = len(lots) + len(draft_invoices)
    completed_count = len(invoices)
    result_count = pending_count if tab == "pending" else completed_count

    # Bill ke form ke dropdowns ke liye: tax rates aur Charges Master
    tax_rates = TaxRate.query.filter(TaxRate.is_deleted == False, TaxRate.is_active == True).order_by(TaxRate.rate_percent).all()
    charges = Charge.query.filter(Charge.is_deleted == False, Charge.is_active == True).order_by(Charge.name).all()

    return render_template(
        "purchase_invoices.html",
        active_nav="purchase_invoices",
        tab=tab,
        lots=lots,
        draft_invoices=draft_invoices,
        invoices=invoices,
        pending_count=pending_count,
        completed_count=completed_count,
        result_count=result_count,
        tax_rates=tax_rates,
        charges=charges,
        today=date.today().isoformat(),
    )


def read_invoice_form():
    # Bill ka form padho aur poori jaanch yahin karo (server par: browser par bharosa nahi).
    # Wapas deta hai: (data, None) agar sab theek, ya (None, "error message") agar kuch galat.
    # Kuch bhi database me tab tak nahi likhte jab tak ye function (data, None) na de.

    # ---- Header ----
    vendor_id = request.form.get("vendor_id", type=int)
    vendor = None
    if vendor_id:
        vendor = Vendor.query.filter_by(id=vendor_id, is_deleted=False).first()
    if vendor is None:
        return None, "Please choose a valid vendor."

    vendor_invoice_no = (request.form.get("vendor_invoice_no") or "").strip()
    if not vendor_invoice_no:
        return None, "Enter the vendor's invoice number."
    if len(vendor_invoice_no) > 50:
        return None, "Vendor invoice number is too long (maximum 50 characters)."

    invoice_date_raw = (request.form.get("invoice_date") or "").strip()
    try:
        invoice_date = datetime.strptime(invoice_date_raw, "%Y-%m-%d").date()
    except ValueError:
        return None, "Enter a valid invoice date."

    # Ek vendor ka same bill number do baar nahi (Cancelled / remove kiye hue bill ko chhod kar)
    duplicate = PurchaseInvoice.query.filter(
        PurchaseInvoice.vendor_id == vendor.id,
        PurchaseInvoice.is_deleted == False,
        PurchaseInvoice.status != "Cancelled",
        db.func.lower(PurchaseInvoice.vendor_invoice_no) == vendor_invoice_no.lower(),
    ).first()
    if duplicate:
        return None, f"Invoice {vendor_invoice_no} of this vendor is already entered ({duplicate.pi_no})."

    remarks = (request.form.get("remarks") or "").strip()[:255]

    # ---- Lines: har lot ka kitna hissa is bill me hai ----
    lines = []              # tayyar PurchaseInvoiceLine objects (abhi database me nahi gaye)
    tax_types = []          # har line ka "intra" / "inter" (sab ek jaise hone chahiye)
    seen_lots = []          # ek lot do baar nahi
    i = 0
    while True:
        gl_id = request.form.get(f"grn_line_id_{i}", type=int)
        if gl_id is None:
            break           # form me aur lines nahi hain

        qty = request.form.get(f"qty_{i}", type=float)
        # qty khaali ya 0 = user ne is lot ko is bill me liya hi nahi; use chhod do
        if qty is not None and qty != 0:
            if qty < 0:
                return None, "Quantity cannot be negative."

            grn_line = db.session.get(GRNLine, gl_id)
            if grn_line is None or grn_line.grn.is_deleted:
                return None, "A selected lot was not found. Please reopen the bill form."
            if gl_id in seen_lots:
                return None, "The same lot is listed twice."
            seen_lots.append(gl_id)

            po = grn_line.grn.po
            po_line = grn_line.po_line
            if po is None or po_line is None or po.vendor_id != vendor.id:
                return None, "A selected lot belongs to a different vendor."

            # Sabse zaroori rule: sirf utni quantity jitni QC me pass hui aur abhi tak bill nahi hui
            material_name = po_line.raw_material.name if po_line.raw_material else "Material"
            billable = grn_line.billable_qty
            if round(qty, 4) > billable:
                return None, (f"{material_name} (lot {grn_line.batch_lot_no}): only {billable:g} can be billed "
                              f"({grn_line.passed_qty:g} passed QC, {grn_line.billed_qty:g} already billed).")

            rate = request.form.get(f"rate_{i}", type=float)
            if rate is None or rate < 0:
                return None, f"Enter a valid rate for {material_name}."

            discount = request.form.get(f"discount_{i}", type=float)
            if discount is None:
                discount = 0
            if discount < 0 or discount > 100:
                return None, f"Discount for {material_name} must be between 0 and 100."

            tax_rate_id = request.form.get(f"tax_rate_id_{i}", type=int)
            tax_rate = None
            if tax_rate_id:
                tax_rate = TaxRate.query.filter_by(id=tax_rate_id, is_deleted=False).first()
            if tax_rate is None:
                return None, f"Choose a tax rate for {material_name}."

            # CGST+SGST ya IGST: vendor ka state aur hamare (delivery warehouse ke) branch ka state same hai ya nahi
            branch = po.warehouse.branch if po.warehouse else None
            if branch is None:
                return None, f"The delivery branch of {po.po_no} is missing."
            if vendor.state_id == branch.state_id:
                tax_types.append("intra")
            else:
                tax_types.append("inter")

            lines.append(PurchaseInvoiceLine(
                grn_line_id=gl_id,
                raw_material_id=po_line.raw_material_id,
                unit_id=po_line.unit_id,
                qty=qty,
                rate=rate,
                discount_percent=discount,
                tax_rate_id=tax_rate.id,
                tax_percent=tax_rate.rate_percent,    # COPY: tax master baad me badle to bhi bill wahi rahe
            ))
        i += 1

    if not lines:
        return None, "Enter a quantity for at least one lot."
    if "intra" in tax_types and "inter" in tax_types:
        return None, "These lots go to branches in different states, so they need separate bills."
    tax_type = tax_types[0]

    # ---- Charges (freight / other): PO jaisa, Charges Master se ----
    charge_rows = []
    j = 0
    while True:
        if f"charge_id_{j}" not in request.form:
            break           # aur charge rows nahi
        charge_id = request.form.get(f"charge_id_{j}", type=int)
        amount = request.form.get(f"charge_amount_{j}", type=float)
        effect = (request.form.get(f"charge_effect_{j}") or "add").strip()

        # Poori khaali row (na charge, na amount) chhod do
        if charge_id is not None or amount is not None:
            charge = None
            if charge_id:
                charge = db.session.get(Charge, charge_id)
            if charge is None or charge.is_deleted or not charge.is_active:
                return None, "Choose a valid charge for every charge row."
            if amount is None or amount <= 0:
                return None, f"Enter an amount above zero for {charge.name}."
            if effect not in ("add", "minus"):
                return None, "Charge effect must be Add or Minus."
            charge_rows.append(PurchaseInvoiceCharge(charge_id=charge.id, amount=round(amount, 2), effect=effect))
        j += 1

    # ---- Totals: server nikalta hai (browser ke dikhaye totals par bharosa nahi), har jagah paise tak round ----
    subtotal = 0
    tax_total = 0
    for line in lines:
        subtotal += line.taxable_amount
        tax_total += line.tax_amount
    charges_total = 0
    for ch in charge_rows:
        charges_total += ch.signed_amount

    subtotal = round(subtotal, 2)
    tax_total = round(tax_total, 2)
    charges_total = round(charges_total, 2)
    total_amount = round(subtotal + tax_total + charges_total, 2)
    if total_amount < 0:
        return None, "The bill total cannot be negative. Check the Minus charges."

    data = {
        "vendor": vendor,
        "vendor_invoice_no": vendor_invoice_no,
        "invoice_date": invoice_date,
        "remarks": remarks,
        "tax_type": tax_type,
        "lines": lines,
        "charge_rows": charge_rows,
        "subtotal": subtotal,
        "tax_total": tax_total,
        "charges_total": charges_total,
        "total_amount": total_amount,
    }
    return data, None


@purchase_invoices_bp.route("/purchase_invoices/add", methods=["POST"])
def purchase_invoices_add():
    data, error = read_invoice_form()
    if error:
        flash(error, "error")
        return redirect(list_url("pending"))

    # PI-2026-001 jaisa number: us saal ke bills gin ke (cancel / remove kiye hue bhi gine jaate hain, number dobara nahi aata)
    year = data["invoice_date"].year
    count = PurchaseInvoice.query.filter(PurchaseInvoice.pi_no.like(f"PI-{year}-%")).count()
    pi_no = f"PI-{year}-{count + 1:03d}"

    invoice = PurchaseInvoice(
        pi_no=pi_no,
        vendor=data["vendor"],
        vendor_invoice_no=data["vendor_invoice_no"],
        invoice_date=data["invoice_date"],
        tax_type=data["tax_type"],
        status="Draft",
        remarks=data["remarks"],
        subtotal=data["subtotal"],
        tax_total=data["tax_total"],
        charges_total=data["charges_total"],
        total_amount=data["total_amount"],
        is_deleted=False,
    )
    db.session.add(invoice)

    # Lines / charges ko bill se jodo aur save karo (SQLAlchemy 2.0 me khud db.session.add likhna padta hai)
    for line in data["lines"]:
        line.invoice = invoice
        db.session.add(line)
    for charge_row in data["charge_rows"]:
        charge_row.invoice = invoice
        db.session.add(charge_row)

    # "Post bill" button dabaya ho to turant post (vendor ledger me Cr), warna Draft
    if (request.form.get("invoice_action") or "draft").strip() == "post":
        post_invoice(invoice)

    db.session.commit()

    if invoice.status == "Posted":
        flash(f"Bill {pi_no} posted: {data['total_amount']:,.2f} added to {data['vendor'].name}'s payable.", "success")
        return redirect(list_url("completed"))
    flash(f"Bill {pi_no} saved as Draft. Post it from the Pending list when it is checked.", "success")
    return redirect(list_url("pending"))


@purchase_invoices_bp.route("/purchase_invoices/post/<int:inv_id>", methods=["POST"])
def purchase_invoices_post(inv_id):
    invoice = PurchaseInvoice.query.filter_by(id=inv_id, is_deleted=False).first_or_404()
    if invoice.status != "Draft":
        flash("Only a draft bill can be posted.", "error")
        return redirect(list_url("completed"))

    post_invoice(invoice)
    db.session.commit()
    flash(f"Bill {invoice.pi_no} posted: {invoice.total_amount:,.2f} added to {invoice.vendor.name}'s payable.", "success")
    return redirect(list_url("completed"))


@purchase_invoices_bp.route("/purchase_invoices/cancel/<int:inv_id>", methods=["POST"])
def purchase_invoices_cancel(inv_id):
    invoice = PurchaseInvoice.query.filter_by(id=inv_id, is_deleted=False).first_or_404()
    if invoice.status == "Cancelled":
        flash("This bill is already cancelled.", "error")
        return redirect(list_url("completed"))

    for purchase_return in invoice.returns:
        if purchase_return.is_deleted or purchase_return.status == "Cancelled":
            continue
        flash(f"{invoice.pi_no} has an active return ({purchase_return.pr_no}). Cancel the return first.", "error")
        return redirect(list_url("completed"))    

    was_posted = invoice.status == "Posted"
    cancel_invoice(invoice)
    db.session.commit()
    if was_posted:
        flash(f"Bill {invoice.pi_no} cancelled. The payable was reversed and its quantity can be billed again.", "success")
    else:
        flash(f"Draft bill {invoice.pi_no} cancelled. Its quantity can be billed again.", "success")
    return redirect(list_url("pending" if not was_posted else "completed"))
