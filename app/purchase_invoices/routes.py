from datetime import date, datetime

from flask import render_template, Blueprint, request, redirect, url_for, flash
from app.extensions import db
from app.models import (
    PurchaseInvoice, PurchaseInvoiceLine, PurchaseInvoiceCharge,
    GRN, TaxRate, Charge,
)
from app.purchase_invoices.posting import post_invoice, cancel_invoice
from app.tax import calc_tax, line_value

purchase_invoices_bp = Blueprint("purchase_invoices", __name__, template_folder="templates")


def list_url(tab="pending"):
    return url_for("purchase_invoices.purchase_invoices_list", tab=tab)


@purchase_invoices_bp.route("/purchase_invoices")
def purchase_invoices_list():
    # Auto-flow: "New invoice" button nahi. Bill ka kaam pichle step (QC) se khud yahan aata hai.
    #   pending   = (1) wo GRN jinka QC poora ho chuka aur bill baaki hai, (2) Draft bills (post baaki)
    #   completed = Posted / Cancelled bills
    # Client rule: ek GRN = ek bill, saari lines, GRN me aayi poori qty (rejected samet).
    tab = (request.args.get("tab") or "pending").strip().lower()
    if tab != "completed":
        tab = "pending"   # ?tab=kuchbhi aaye to bhi pending

    # GRN "Closed" = uski saari lines ka final QC ho gaya (inward_qc/routes.py yahi status lagata hai)
    closed_grns = GRN.query.filter(GRN.is_deleted == False, GRN.status == "Closed").order_by(GRN.id.desc()).all()
    ready_grns = []                    # wo GRN jinka bill abhi nahi bana
    for grn in closed_grns:
        if grn.billing_invoice is None:
            ready_grns.append(grn)

    base = PurchaseInvoice.query.filter(PurchaseInvoice.is_deleted == False)
    draft_invoices = base.filter(PurchaseInvoice.status == "Draft").order_by(PurchaseInvoice.id.desc()).all()
    invoices = base.filter(PurchaseInvoice.status != "Draft").order_by(PurchaseInvoice.id.desc()).all()

    # F3: PO-wise grouping — ek PO ke bill / GRN saath-saath (naya PO pehle, PO ke andar naya pehle)
    def po_key(inv):
        po = inv.po
        return (-(po.id if po else 0), -inv.id)
    ready_grns.sort(key=lambda grn: (-grn.po_id, -grn.id))
    draft_invoices.sort(key=po_key)
    invoices.sort(key=po_key)

    # Pending tab ek hi list: har PO ke neeche pehle uske bill-ke-liye-tayyar GRN, phir uske Draft bills
    pending_items = []
    for grn in ready_grns:
        pending_items.append({"kind": "grn", "po": grn.po, "po_id": grn.po_id, "grn": grn, "inv": None, "order": 0, "rid": grn.id})
    for inv in draft_invoices:
        po = inv.po
        pending_items.append({"kind": "draft", "po": po, "po_id": po.id if po else 0, "grn": None, "inv": inv, "order": 1, "rid": inv.id})
    pending_items.sort(key=lambda item: (-item["po_id"], item["order"], -item["rid"]))

    pending_count = len(ready_grns) + len(draft_invoices)
    completed_count = len(invoices)
    result_count = pending_count if tab == "pending" else completed_count

    # Bill ke form ke dropdowns ke liye: tax rates aur Charges Master
    tax_rates = TaxRate.query.filter(TaxRate.is_deleted == False, TaxRate.is_active == True).order_by(TaxRate.rate_percent).all()
    charges = Charge.query.filter(Charge.is_deleted == False, Charge.is_active == True).order_by(Charge.name).all()

    return render_template(
        "purchase_invoices.html",
        active_nav="purchase_invoices",
        tab=tab,
        ready_grns=ready_grns,
        draft_invoices=draft_invoices,
        pending_items=pending_items,
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

    # ---- GRN: bill ek poore GRN ka banta hai. Vendor, lines aur qty GRN se aate hain (form se nahi) ----
    grn_id = request.form.get("grn_id", type=int)
    grn = db.session.get(GRN, grn_id) if grn_id else None
    if grn is None or grn.is_deleted:
        return None, "The goods receipt (GRN) for this bill was not found. Please reopen the bill form."
    if grn.status != "Closed":
        return None, f"{grn.grn_no} is not ready to bill: finish the quality check of all its lots first."
    existing = grn.billing_invoice
    if existing is not None:
        return None, f"{grn.grn_no} already has a bill ({existing.pi_no}). Cancel it first to bill again."

    po = grn.po
    vendor = po.vendor if po else None
    if po is None or vendor is None or vendor.is_deleted:
        return None, f"The vendor of {grn.grn_no} was not found."
    branch = po.warehouse.branch if po.warehouse else None
    if branch is None:
        return None, f"The delivery branch of {po.po_no} is missing."
    # CGST+SGST ya IGST: vendor ka state aur hamare (delivery warehouse ke) branch ka state same hai ya nahi
    tax_type = "intra" if vendor.state_id == branch.state_id else "inter"

    # ---- Header ----
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

    # ---- Form se har lot ka rate aur tax: grn_line_id_i, rate_i, tax_rate_id_i. Qty form se nahi aati. ----
    wanted = {}
    i = 0
    while True:
        gl_id = request.form.get(f"grn_line_id_{i}", type=int)
        if gl_id is None:
            break
        wanted[gl_id] = (request.form.get(f"rate_{i}", type=float), request.form.get(f"tax_rate_id_{i}", type=int))
        i += 1

    # ---- Lines: GRN ki HAR line, poori received qty (rejected samet) ----
    specs = []              # (grn_line, po_line, qty, rate, tax_rate): objects abhi nahi bana rahe (validation baad me save)
    for grn_line in grn.lines:
        po_line = grn_line.po_line
        if po_line is None:
            return None, "A lot of this GRN has no purchase order line."
        material_name = po_line.raw_material.name if po_line.raw_material else "Material"
        if grn_line.id not in wanted:
            return None, "The bill form is out of date. Please close it and open it again."
        rate, tax_rate_id = wanted[grn_line.id]
        if rate is None or rate < 0:
            return None, f"Enter a valid rate for {material_name}."
        tax_rate = TaxRate.query.filter_by(id=tax_rate_id, is_deleted=False).first() if tax_rate_id else None
        if tax_rate is None:
            return None, f"Choose a tax rate for {material_name}."
        if not grn_line.received_qty or grn_line.received_qty <= 0:
            return None, f"{material_name}: nothing was received on this lot."
        specs.append((grn_line, po_line, grn_line.received_qty, rate, tax_rate))
    if not specs:
        return None, f"{grn.grn_no} has no lots to bill."

    # ---- Charges (freight / other): PO jaisa, Charges Master se ----
    charge_specs = []       # (charge, amount, effect)
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
            charge_specs.append((charge, round(amount, 2), effect))
        j += 1

    # ---- Totals: server nikalta hai (browser ke dikhaye totals par bharosa nahi). GST items + charges ke total par (app/tax.py) ----
    charges_net = 0
    for _charge, amount, effect in charge_specs:
        charges_net += -amount if effect == "minus" else amount
    result = calc_tax(
        [(line_value(qty, rate), tax_rate.rate_percent) for _gl, _pl, qty, rate, tax_rate in specs],
        round(charges_net, 2),
    )
    if result["grand_total"] < 0:
        return None, "The bill total cannot be negative. Check the Minus charges."

    # ---- Sab theek: ab objects banao (pehle banate to SQLAlchemy unhe invoice ki list me jod deta, galat jagah) ----
    lines = []
    for grn_line, po_line, qty, rate, tax_rate in specs:
        lines.append(PurchaseInvoiceLine(
            grn_line_id=grn_line.id,
            raw_material_id=po_line.raw_material_id,
            unit_id=po_line.unit_id,
            qty=qty,
            rate=rate,
            discount_percent=0,
            tax_rate_id=tax_rate.id,
            tax_percent=tax_rate.rate_percent,    # COPY: tax master baad me badle to bhi bill wahi rahe
        ))
    charge_rows = [PurchaseInvoiceCharge(charge_id=charge.id, amount=amount, effect=effect) for charge, amount, effect in charge_specs]

    data = {
        "grn": grn,
        "vendor": vendor,
        "vendor_invoice_no": vendor_invoice_no,
        "invoice_date": invoice_date,
        "remarks": remarks,
        "tax_type": tax_type,
        "lines": lines,
        "charge_rows": charge_rows,
        "subtotal": result["items_total"],
        "tax_total": result["tax_total"],
        "charges_total": result["charges_net"],
        "total_amount": result["grand_total"],
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
        grn=data["grn"],
        vendor_invoice_no=data["vendor_invoice_no"],
        invoice_date=data["invoice_date"],
        tax_type=data["tax_type"],
        status="Draft",
        remarks=data["remarks"],
        subtotal=data["subtotal"],
        tax_total=data["tax_total"],
        charges_total=data["charges_total"],
        total_amount=data["total_amount"],
        gst_on_charges=True,
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
        flash(f"Bill {invoice.pi_no} cancelled. The payable was reversed and the GRN can be billed again.", "success")
    else:
        flash(f"Draft bill {invoice.pi_no} cancelled. The GRN can be billed again.", "success")
    return redirect(list_url("pending" if not was_posted else "completed"))
