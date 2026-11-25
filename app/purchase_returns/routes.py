from datetime import datetime

from flask import render_template, Blueprint, request, redirect, url_for, flash
from app.extensions import db
from app.auth import service as auth_service
from app.models import (
    PurchaseReturn, PurchaseReturnLine, PurchaseReturnCharge,
    PurchaseInvoice, PurchaseInvoiceLine, Charge,
)
from app.purchase_invoices.posting import post_return, cancel_return
from app.tax import calc_tax
from app.inventory.posting import InventoryError

purchase_returns_bp = Blueprint("purchase_returns", __name__, template_folder="templates")

def read_return_form():
    # Return ka form padho aur poori jaanch yahin karo.
    # Wapas deta hai: (data, None) agar sab theek, ya (None, "error message") agar kuch galat.
    # Database me kuch tabhi likhte hain jab ye (data, None) de.

    # ---- Header: kaun sa bill, kab, kyun ----
    invoice_id = request.form.get('invoice_id', type=int)
    invoice = None
    if invoice_id:
        invoice = PurchaseInvoice.query.filter_by(id=invoice_id, is_deleted = False).first()
    if invoice is None:
        return None, "Choose a valid bill for the return."
    if invoice.status != "Posted":
        return None, "A return can be made only against a posted bill."        

    return_date_raw = (request.form.get('return_date') or "").strip()
    try:
        return_date = datetime.strptime(return_date_raw, "%Y-%m-%d").date()
    except ValueError:
        return None, "Enter a valid return date."
    if return_date < invoice.invoice_date:
        return None, "The return date cannot be before the bill date."

    reason = (request.form.get('reason') or "").strip()
    if not reason:
        return None, "Enter the reason for the return."
    if len(reason) > 255:
        return None, "The reason is too long (maximum 255 characters)."

    # ---- Lines: bill ki kaun si line se kitna wapas, aur kis me se (Passed ya Rejected) ----
    # Har item ek dictionary hai (model object nahi): PurchaseReturnLine object abhi banaya to wo
    # invoice_line.return_lines me chala jaata aur returned qty galat ginta. Object tab banenge jab sab jaanch pass ho.
    line_rows = []
    seen_ids = []
    i = 0
    while True:
        line_id = request.form.get(f'invoice_line_id_{i}', type=int)
        if line_id is None:
            break

        # Ek bill line se do tarah ka maal wapas ja sakta hai: qty_N = passed me se, rejected_qty_N = rejected me se
        amounts = {"passed": request.form.get(f"qty_{i}", type=float),
                   "rejected": request.form.get(f"rejected_qty_{i}", type=float)}
        # qty khaali ya 0 = ye line return me nahi hai, chhod do
        if any(value not in (None, 0) for value in amounts.values()):
            invoice_line = db.session.get(PurchaseInvoiceLine, line_id)
            if invoice_line is None or invoice_line.invoice_id != invoice.id:
                return None, "A selected line does not belong to this bill."
            if line_id in seen_ids:
                return None, "The same bill line is listed twice."
            seen_ids.append(line_id)

            material_name = invoice_line.raw_material.name if invoice_line.raw_material else "Material"
            unit_code = invoice_line.unit.code if invoice_line.unit else ""
            for source in ("passed", "rejected"):
                qty = amounts[source]
                if qty is None or qty == 0:
                    continue
                if qty < 0:
                    return None, "Quantity cannot be negative."
                can_return = invoice_line.returnable_passed if source == "passed" else invoice_line.returnable_rejected
                if round(qty, 4) > can_return:
                    return None, (f"{material_name}: only {can_return:g} {unit_code} can still be returned from the {source} goods "
                                  f"({invoice_line.qty:g} on the bill, {invoice_line.returned_qty:g} already returned).")

                # Paisa bill line ke rate / discount / tax se (PurchaseReturnLine ki properties wala hi formula)
                taxable = round(qty * invoice_line.rate * (1 - invoice_line.discount_percent / 100), 2)
                tax = round(taxable * invoice_line.tax_percent / 100, 2)
                line_rows.append({"invoice_line": invoice_line, "qty": qty, "source": source, "taxable": taxable, "tax": tax})
        i += 1

    if not line_rows:
        return None, "Enter a quantity for at least one line."

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
            charge_rows.append(PurchaseReturnCharge(charge_id=charge.id, amount=round(amount, 2), effect=effect))
        j += 1

    # ---- Totals: server nikalta hai. GST goods + charges ke total par (app/tax.py), charge lines me value ke anupaat se ----
    charges_net = 0
    for charge_row in charge_rows:
        charges_net += charge_row.signed_amount
    result = calc_tax([(row["taxable"], row["invoice_line"].tax_percent) for row in line_rows], round(charges_net, 2))

    subtotal = result["items_total"]
    tax_total = result["tax_total"]
    charges_total = result["charges_net"]
    total_amount = result["grand_total"]
    if total_amount < 0:
        return None, "The charges are more than the value of the goods. Check the amounts."

    data = {
        "invoice": invoice,
        "return_date": return_date,
        "reason": reason,
        "line_rows": line_rows,
        "charge_rows": charge_rows,
        "subtotal": subtotal,
        "tax_total": tax_total,
        "charges_total": charges_total,
        "total_amount": total_amount,
    }
    return data, None    

@purchase_returns_bp.route('/purchase_returns')
def purchase_return_list():
    # Purchase return page: saare returns ki list. Pending / Completed tabs nahi: return koi "baaki kaam" nahi,
    # jab maal wapas bhejna ho tabhi banta hai (Purchase invoice ke Posted bill se).
    returns = PurchaseReturn.query.filter(PurchaseReturn.is_deleted == False).order_by(PurchaseReturn.id.desc()).all()
    # F3: PO-wise grouping — ek PO ke returns saath-saath (naya PO pehle, PO ke andar naya return pehle)
    def po_key(purchase_return):
        po = purchase_return.invoice.po if purchase_return.invoice else None
        return (-(po.id if po else 0), -purchase_return.id)
    returns.sort(key=po_key)
    return render_template(
        "purchase_returns.html", 
        active_nav="purchase_returns", 
        returns=returns
        )

@purchase_returns_bp.route('/purchase_returns/add', methods=['POST'])
def purchase_returns_add():
    data, error = read_return_form()
    if error :
         # Return ka form Purchase invoice page par hai, isliye galti par wahin wapas
        flash(error, "error")
        return redirect(url_for("purchase_invoices.purchase_invoices_list", tab="completed"))

    # PR-2026-001 jaisa number: us saal ke returns gin ke (Cancelled bhi gine jaate hain, number dobara nahi aata)
    year = data["return_date"].year
    count = PurchaseReturn.query.filter(PurchaseReturn.pr_no.like(f"PR-{year}-%")).count()
    pr_no = f"PR-{year}-{count + 1:03d}"

    purchase_return = PurchaseReturn(
        pr_no=pr_no,
        invoice = data["invoice"],
        return_date = data["return_date"],
        reason = data["reason"],
        status = "Posted",
        subtotal = data["subtotal"],
        tax_total = data["tax_total"],
        charges_total = data["charges_total"],
        total_amount = data["total_amount"],
        gst_on_charges = True,
        created_by_id = auth_service.actor_id(),     # W1: kisne banaya
        is_deleted = False,
    )
    db.session.add(purchase_return)

    # Lines / charges ab banao (jaanch pass ho chuki) aur return se jodo.
    # SQLAlchemy 2.0 me bachche ko db.session.add khud likhna padta hai.
    for row in data["line_rows"]:
        db.session.add(PurchaseReturnLine(
            purchase_return=purchase_return,
            invoice_line=row["invoice_line"],
            qty=row["qty"],
            source=row["source"],
        ))
    for charge_row in data["charge_rows"]:
        charge_row.purchase_return = purchase_return
        db.session.add(charge_row)

    # Vendor ledger me paisa ghatao (posting.py), phir ek hi commit: sab kuch ya kuch nahi
    try:
        post_return(purchase_return)
    except InventoryError as error:
        db.session.rollback()
        flash(str(error), "error")
        return redirect(url_for("purchase_invoices.purchase_invoices_list", tab="completed"))
    db.session.commit()

    vendor_name = data["invoice"].vendor.name
    flash(f"Return {pr_no} posted. {vendor_name} will credit you ₹{data['total_amount']:,.2f}.", "success")
    # Purchase invoice ka Edit wala user (jise Purchase return page ka View nahi) save ke baad 403 page na dekhe -> invoice page par wapas
    from app.auth import registry as auth_registry     # auth_service upar module level par import hai
    if auth_service.user_can(auth_service.current(), "purchase_returns", auth_registry.LEVEL_VIEW):
        return redirect(url_for("purchase_returns.purchase_return_list"))
    return redirect(url_for("purchase_invoices.purchase_invoices_list", tab="completed"))


@purchase_returns_bp.route("/purchase_returns/cancel/<int:ret_id>", methods=["POST"])
def purchase_returns_cancel(ret_id):
    purchase_return = PurchaseReturn.query.filter_by(id=ret_id, is_deleted=False).first_or_404()
    if purchase_return.status == "Cancelled":
        flash("This return is already cancelled.", "error")
        return redirect(url_for("purchase_returns.purchase_return_list"))

    cancel_return(purchase_return)
    purchase_return.cancelled_by_id = auth_service.actor_id()    # W1: kisne cancel kiya
    db.session.commit()
    flash(f"Return {purchase_return.pr_no} cancelled. The credit of ₹{purchase_return.total_amount:,.2f} was taken back, "
          f"and the quantity can be returned again.", "success")
    return redirect(url_for("purchase_returns.purchase_return_list"))