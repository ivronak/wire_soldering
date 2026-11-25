from flask import render_template, Blueprint, redirect, url_for, request, flash, current_app, send_from_directory
from app.timeutil import ist_now
from app.models import PurchaseOrder, PurchaseOrderLine, Vendor, Warehouse, RawMaterial, Unit, TaxRate, PaymentTerm, Charge, PurchaseOrderCharge, PurchaseOrderRevision
from app.extensions import db
from app.auth import service as auth_service
from app.purchase_orders.docket import build_docket, format_qty, format_rate, format_reading, format_inr
from datetime import datetime
import os
from werkzeug.utils import secure_filename
from werkzeug.security import safe_join


purchase_orders_bp = Blueprint("purchase_orders", __name__, template_folder="templates")

# Docket template ke filters: {{ x|qty }} quantity, {{ x|rate }} rate, {{ x|reading }} lab ka number, {{ x|inr }} paisa (Indian grouping)
purchase_orders_bp.add_app_template_filter(format_qty, "qty")
purchase_orders_bp.add_app_template_filter(format_rate, "rate")
purchase_orders_bp.add_app_template_filter(format_reading, "reading")
purchase_orders_bp.add_app_template_filter(format_inr, "inr")

ALLOWED_INVOICE_EXTENSIONS ={"pdf", "png", "jpg", "jpeg"}

def _allowed_invoice_file(filename):
    return "." in filename and filename.rsplit(".",1)[1].lower() in ALLOWED_INVOICE_EXTENSIONS

@purchase_orders_bp.route('/purchase_orders')
def purchase_orders_list():
    # §10.6: list do hisson me — "pending" (kaam baaki) aur "completed" (kaam khatam)
    # URL me ?tab=completed aaye to completed, warna pending (default)
    tab = (request.args.get("tab") or "pending").strip().lower()

    # PO step ka kaam = banana + confirm karna. Isliye:
    # pending = Draft (confirm baaki); confirm hote hi PO "completed" — uska maal ab GRN page ke Pending me dikhta hai
    pending_statuses = ["Draft"]
    completed_statuses = ["Open", "Partial", "Closed", "Cancelled"]

    # Base query ek baar banao — .filter() naya query deta hai, base ko nahi badalta
    base = PurchaseOrder.query.filter(PurchaseOrder.is_deleted == False)
    pending_count = base.filter(PurchaseOrder.status.in_(pending_statuses)).count()
    completed_count = base.filter(PurchaseOrder.status.in_(completed_statuses)).count()

    if tab == "completed":
        statuses = completed_statuses
    else:
        tab = "pending"  # ?tab=kuchbhi aaye to bhi pending hi dikhao
        statuses = pending_statuses

    orders = base.filter(PurchaseOrder.status.in_(statuses)).order_by(PurchaseOrder.id.desc()).all()
    total_count = len(orders)

    vendors = Vendor.query.filter(Vendor.is_deleted == False, Vendor.is_active == True).all()
    # PO ka warehouse = jahan QC ke baad maal rakha jaayega, isliye sirf store (RM) type; QC Hold GRN me khud lagta hai
    warehouses = Warehouse.query.filter(Warehouse.is_deleted == False, Warehouse.is_active == True, Warehouse.warehouse_type == "RM").all()
    raw_materials = RawMaterial.query.filter(RawMaterial.is_deleted == False, RawMaterial.is_active == True).all()
    units = Unit.query.filter(Unit.is_active == True, Unit.is_deleted == False).all()
    tax_rates = TaxRate.query.filter(TaxRate.is_active == True, TaxRate.is_deleted == False).all()
    charges = Charge.query.filter(Charge.is_deleted == False, Charge.is_active == True).order_by(Charge.name).all()

    
    return render_template(
        "purchase_orders.html",
        active_nav='purchase_orders',
        orders=orders,
        tab=tab,
        pending_count=pending_count,
        completed_count=completed_count,
        total_count=total_count,
        result_count=total_count,
        vendors=vendors,
        warehouses=warehouses,
        raw_materials=raw_materials,
        units=units,
        tax_rates=tax_rates,
        charges=charges,
        # Payment terms dropdown ab Payment Terms Master se — sirf live (deleted nahi, active)
        payment_terms=PaymentTerm.query.filter(PaymentTerm.is_deleted == False, PaymentTerm.is_active == True).order_by(PaymentTerm.name).all(),
    )


@purchase_orders_bp.route('/purchase_orders/add', methods=['POST'])
def purchase_orders_add():
    vendor_id = int(request.form.get('vendor_id')) if (request.form.get('vendor_id')or "").strip() else None
    warehouse_id = int(request.form.get('warehouse_id')) if (request.form.get('warehouse_id') or "").strip() else None
    po_date_raw = (request.form.get('po_date') or "").strip()
    expected_raw = (request.form.get('expected_delivery_date') or "").strip()
    remarks = (request.form.get('remarks') or "").strip()
    # Payment terms ab master se aata hai (OPTIONAL) — form se id
    payment_terms_id = request.form.get('payment_terms_id', type=int)
    # Freight ab alag field nahi: Charges Master ki line se aata hai (neeche charge_id_N). PurchaseOrder.freight column
    # sirf purani POs ke display ke liye bacha hai; nayi PO me wo column ka default 0 hi rehta hai.


    if not vendor_id or not warehouse_id or not po_date_raw:
        return redirect(url_for('purchase_orders.purchase_orders_list'))

    # Payment terms optional hai — par agar diya hai to valid (deleted nahi) hona chahiye
    if payment_terms_id and not PaymentTerm.query.filter(PaymentTerm.id == payment_terms_id, PaymentTerm.is_deleted == False).first():
        flash("Please select valid payment terms.", "error")
        return redirect(url_for('purchase_orders.purchase_orders_list'))

    chosen = db.session.get(Warehouse, warehouse_id)
    if chosen is None or chosen.is_deleted or chosen.warehouse_type != "RM":
        flash("Choose a store (raw material) warehouse for the purchase order.", "error")
        return redirect(url_for('purchase_orders.purchase_orders_list'))

    po_date = datetime.strptime(po_date_raw, "%Y-%m-%d").date()
    expected_delivery_date = datetime.strptime(expected_raw, "%Y-%m-%d").date() if expected_raw  else None

    #po_no auto-generate: "PO-<saal>-<agla number>"
    year = po_date.year
    count = PurchaseOrder.query.filter(PurchaseOrder.po_no.like(f"PO-{year}-%")).count()
    po_no = f"PO-{year}-{count + 1:03d}"

    po = PurchaseOrder(
        po_no=po_no,
        vendor_id=vendor_id,
        warehouse_id=warehouse_id,
        po_date=po_date,
        expected_delivery_date=expected_delivery_date,
        status="Draft",
        remarks=remarks,
        payment_terms_id=payment_terms_id,
        created_by_id=auth_service.actor_id(),       # W1: kisne banayi (login user, apne aap)
        is_deleted=False,
    )
    db.session.add(po)
    db.session.flush()

    i=0
    while True:
        material_id_raw = (request.form.get(f"material_id_{i}") or "").strip()
        qty_raw = (request.form.get(f'ordered_qty_{i}') or "").strip()
        rate_raw = (request.form.get(f'rate_{i}') or "").strip()
        unit_id_raw = (request.form.get(f'unit_id_{i}') or "").strip()
        tax_rate_id_raw = (request.form.get(f'tax_rate_id_{i}') or "").strip()

        if not material_id_raw and not qty_raw and not rate_raw:
            break

        if material_id_raw and qty_raw and rate_raw and unit_id_raw and tax_rate_id_raw:
            db.session.add(PurchaseOrderLine(
                po_id=po.id,
                raw_material_id=int(material_id_raw),
                ordered_qty=float(qty_raw),
                unit_id=int(unit_id_raw),
                tax_rate_id=int(tax_rate_id_raw),
                rate=float(rate_raw),
                discount_percent=0,
            ))
        i +=1

    j=0
    while True:
        charge_id_raw = (request.form.get(f'charge_id_{j}') or "").strip()
        amount_raw = (request.form.get(f'charge_amount_{j}') or "").strip()
        effect = (request.form.get(f'charge_effect_{j}') or "").strip()
        if not charge_id_raw and not amount_raw:
            break
        if charge_id_raw and amount_raw and effect in ("add", "minus"):
            amount = float(amount_raw)
            charge = Charge.query.get(int(charge_id_raw))
            if charge and not charge.is_deleted and charge.is_active and amount > 0:
                db.session.add(PurchaseOrderCharge(
                    po_id=po.id,
                    charge_id=charge.id,
                    amount=amount,
                    effect=effect,
                )) 
        j+=1

    db.session.commit()
    flash(f"Purchase Order {po_no} saved.", "success")
    return redirect(url_for('purchase_orders.purchase_orders_list'))

def read_confirm_edits(po):
    """Confirm panel me vendor ke kehne par badle hue rate / qty / tax / charges padhta hai (F10).
    Pehle sab check karta hai, kuch save nahi karta. Return: (errors, changes, notes)
    changes = [(object, field, new_value)], notes = revision ke liye "purana -> naya" ki lines."""
    errors = []
    changes = []
    notes = []
    if request.form.get("line_id_0") is None:
        return errors, changes, notes      # panel ke edit fields aaye hi nahi — kuch badla nahi

    lines_by_id = {line.id: line for line in po.lines}
    i = 0
    while request.form.get(f"line_id_{i}") is not None:
        line = lines_by_id.get(request.form.get(f"line_id_{i}", type=int))
        qty = request.form.get(f"line_qty_{i}", type=float)
        rate = request.form.get(f"line_rate_{i}", type=float)
        tax_id = request.form.get(f"line_tax_{i}", type=int)
        i += 1
        if line is None:
            errors.append("One of the lines does not belong to this purchase order.")
            continue
        name = line.raw_material.name if line.raw_material else "Item"
        tax = TaxRate.query.get(tax_id) if tax_id else None
        if qty is None or qty <= 0:
            errors.append(f"{name}: quantity must be more than 0.")
            continue
        if rate is None or rate < 0:
            errors.append(f"{name}: rate cannot be negative.")
            continue
        if tax is None or tax.is_deleted:
            errors.append(f"{name}: please choose a valid tax rate.")
            continue

        parts = []
        if round(qty, 4) != round(line.ordered_qty, 4):
            parts.append(f"qty {format_qty(line.ordered_qty)} \u2192 {format_qty(qty)}")
            changes.append((line, "ordered_qty", qty))
        if round(rate, 4) != round(line.rate, 4):
            parts.append(f"rate {format_rate(line.rate)} \u2192 {format_rate(rate)}")
            changes.append((line, "rate", rate))
        if tax.id != line.tax_rate_id:
            old_percent = line.tax_rate.rate_percent if line.tax_rate else 0
            parts.append(f"tax {format_qty(old_percent)}% \u2192 {format_qty(tax.rate_percent)}%")
            changes.append((line, "tax_rate_id", tax.id))
        if parts:
            notes.append(f"{name}: " + ", ".join(parts))

    charges_by_id = {charge_line.id: charge_line for charge_line in po.charge_lines}
    j = 0
    while request.form.get(f"charge_row_id_{j}") is not None:
        charge_line = charges_by_id.get(request.form.get(f"charge_row_id_{j}", type=int))
        amount_raw = (request.form.get(f"charge_row_amount_{j}") or "").strip()
        effect = (request.form.get(f"charge_row_effect_{j}") or "").strip()
        j += 1
        if charge_line is None:
            errors.append("One of the charges does not belong to this purchase order.")
            continue
        name = charge_line.charge.name if charge_line.charge else "Charge"
        if effect not in ("add", "minus"):
            errors.append(f"{name}: please choose Add or Minus.")
            continue
        if amount_raw == "":
            # Amount khaali = vendor ne ye charge hata diya
            notes.append(f"{name}: removed (was {format_inr(charge_line.amount)})")
            changes.append((charge_line, "remove", None))
            continue
        try:
            amount = float(amount_raw)
        except ValueError:
            errors.append(f"{name}: amount must be a number.")
            continue
        if amount < 0:
            errors.append(f"{name}: amount cannot be negative.")
            continue
        parts = []
        if round(amount, 2) != round(charge_line.amount, 2):
            parts.append(f"amount {format_inr(charge_line.amount)} \u2192 {format_inr(amount)}")
            changes.append((charge_line, "amount", amount))
        if effect != charge_line.effect:
            parts.append(f"{charge_line.effect} \u2192 {effect}")
            changes.append((charge_line, "effect", effect))
        if parts:
            notes.append(f"{name}: " + ", ".join(parts))
    return errors, changes, notes


@purchase_orders_bp.route('/purchase_orders/confirm/<int:po_id>', methods=['POST'])
def purchase_orders_confirm(po_id):
    po = PurchaseOrder.query.get_or_404(po_id)

    if po.status != "Draft":
        return redirect(url_for('purchase_orders.purchase_orders_list'))

    vendor_invoice_no = (request.form.get('vendor_invoice_no') or "").strip()
    invoice_date_raw = (request.form.get('vendor_invoice_date') or "").strip()
    vendor_invoice_date = datetime.strptime(invoice_date_raw, "%Y-%m-%d").date() if invoice_date_raw else None

    invoice_file = request.files.get('invoice_file')
    if not invoice_file or not invoice_file.filename:
        flash("Please attach the vendor's invoice/bill copy before confirming.", "error")
        return redirect(url_for('purchase_orders.purchase_orders_list'))

    if not _allowed_invoice_file(invoice_file.filename):
        flash("Invoice file must be PDF, PNG or JPG.", "error")
        return redirect(url_for('purchase_orders.purchase_orders_list'))

    # Vendor ne kuch badla ho to panel ke edits pehle check karo — galti ho to file bhi save nahi hogi, PO Draft hi rahegi
    edit_errors, edit_changes, edit_notes = read_confirm_edits(po)
    if edit_errors:
        flash(" ".join(edit_errors), "error")
        return redirect(url_for('purchase_orders.purchase_orders_list'))

    folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'purchase_orders', str(po_id))
    os.makedirs(folder, exist_ok=True)
    safe_name = secure_filename(invoice_file.filename)
    invoice_file.save(os.path.join(folder, safe_name))
    po.vendor_invoice_file = 'purchase_orders/' + str(po_id) + '/' + safe_name

    for target, field, new_value in edit_changes:
        if field == "remove":
            db.session.delete(target)       # sirf is Draft PO ki ek charge line; kya hata, revision note me likha rehta hai
        else:
            setattr(target, field, new_value)
    if edit_notes:
        db.session.add(PurchaseOrderRevision(po_id=po.id, note="\n".join(edit_notes)))
    po.gst_on_charges = True                 # confirm ke baad PO nayi GST rule se (items + charges par) chalti hai

    po.vendor_invoice_no = vendor_invoice_no or None
    po.vendor_invoice_date = vendor_invoice_date        
    po.status = "Open"
    po.confirmed_by_id = auth_service.actor_id()       # W1: kisne confirm ki
    db.session.commit()
    # Confirm ke baad PO pending tab se hat jaata hai — user ko batao wo kahan gaya (GRN page ke Pending me)
    flash(f"Purchase Order {po.po_no} confirmed — it is now waiting for goods on the GRN page.", "success")
    return redirect(url_for('purchase_orders.purchase_orders_list'))

@purchase_orders_bp.route('/purchase_orders/short_close/<int:po_id>', methods=['POST'])
def purchase_orders_short_close(po_id):
    po = PurchaseOrder.query.get_or_404(po_id)

    # Sirf Open/Partial PO short-close ho sakti hai — Draft confirm hi nahi hui,
    # Closed to poori mil chuki (short-close ka matlab hi nahi), Cancelled pehle se band hai
    if po.status not in ("Open", "Partial"):
        return redirect(url_for('purchase_orders.purchase_orders_list'))

    reason = (request.form.get('short_close_reason') or "").strip()
    if not reason:
        flash("Please give a reason to short close this purchase order.", "error")
        return redirect(url_for('purchase_orders.purchase_orders_list'))

    po.status = "Cancelled"
    po.short_close_reason = reason
    po.short_closed_by_id = auth_service.actor_id()    # W1: kisne short close ki
    db.session.commit()
    flash(f"Purchase Order {po.po_no} short closed.", "success")
    return redirect(url_for('purchase_orders.purchase_orders_list'))

@purchase_orders_bp.route('/purchase_orders/<int:po_id>/print')
def purchase_orders_print(po_id):
    po = PurchaseOrder.query.get_or_404(po_id)

    if po.is_deleted:
        return redirect(url_for("purchase_orders.purchase_orders_list"))
    return render_template("purchase_order_print.html", po=po)

@purchase_orders_bp.route('/purchase_orders/<int:po_id>/docket')
def purchase_orders_docket(po_id):
    # Procurement docket: is ek PO ke saare documents (GRN, QC, memo, bill, return) ek read-only A4 page par.
    # Kuch save nahi hota; data jama karna docket.py ka kaam hai, yahan sirf route + template.
    po = PurchaseOrder.query.get_or_404(po_id)
    if po.is_deleted:
        return redirect(url_for("purchase_orders.purchase_orders_list"))

    # Vendor invoice ki file DB me likhi ho par server par na mile to dead link nahi dikhana
    # safe_join wahi jaanch karta hai jo file khulne wala route karta hai (../ jaise raaste yahan bhi "nahi" maane jaate)
    invoice_file_ok = False
    if po.vendor_invoice_file:
        file_path = safe_join(current_app.config['UPLOAD_FOLDER'], po.vendor_invoice_file)
        invoice_file_ok = file_path is not None and os.path.isfile(file_path)

    return render_template(
        "purchase_order_docket.html",
        po=po,
        docket=build_docket(po),
        invoice_file_ok=invoice_file_ok,
        printed_at=ist_now(),   # paper docket ko "kab ka" pata chale
    )

@purchase_orders_bp.route('/purchase_orders/<int:po_id>/invoice')
def purchase_orders_invoice(po_id):
    po = PurchaseOrder.query.get_or_404(po_id)
    if not po.vendor_invoice_file:
        return redirect(url_for('purchase_orders.purchase_orders_list'))
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], po.vendor_invoice_file)        