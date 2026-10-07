from flask import render_template, Blueprint, redirect, url_for, request, flash, current_app, send_from_directory
from app.models import PurchaseOrder, PurchaseOrderLine, Vendor, Warehouse, RawMaterial, Unit, TaxRate, PaymentTerm, Charge, PurchaseOrderCharge
from app.extensions import db
from datetime import datetime
import os
from werkzeug.utils import secure_filename


purchase_orders_bp = Blueprint("purchase_orders", __name__, template_folder="templates")

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
    warehouses = Warehouse.query.filter(Warehouse.is_deleted == False, Warehouse.is_active == True).all()
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
    freight = float(request.form.get('freight')) if (request.form.get('freight') or "").strip() else 0


    if not vendor_id or not warehouse_id or not po_date_raw:
        return redirect(url_for('purchase_orders.purchase_orders_list'))

    # Payment terms optional hai — par agar diya hai to valid (deleted nahi) hona chahiye
    if payment_terms_id and not PaymentTerm.query.filter(PaymentTerm.id == payment_terms_id, PaymentTerm.is_deleted == False).first():
        flash("Please select valid payment terms.", "error")
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
        freight=freight,
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

    folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'purchase_orders', str(po_id))
    os.makedirs(folder, exist_ok=True)
    safe_name = secure_filename(invoice_file.filename)
    invoice_file.save(os.path.join(folder, safe_name))
    po.vendor_invoice_file = 'purchase_orders/' + str(po_id) + '/' + safe_name

    po.vendor_invoice_no = vendor_invoice_no or None
    po.vendor_invoice_date = vendor_invoice_date        
    po.status = "Open"
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
    db.session.commit()
    flash(f"Purchase Order {po.po_no} short closed.", "success")
    return redirect(url_for('purchase_orders.purchase_orders_list'))

@purchase_orders_bp.route('/purchase_orders/<int:po_id>/print')
def purchase_orders_print(po_id):
    po = PurchaseOrder.query.get_or_404(po_id)

    if po.is_deleted:
        return redirect(url_for("purchase_orders.purchase_orders_list"))
    return render_template("purchase_order_print.html", po=po)

@purchase_orders_bp.route('/purchase_orders/<int:po_id>/invoice')
def purchase_orders_invoice(po_id):
    po = PurchaseOrder.query.get_or_404(po_id)
    if not po.vendor_invoice_file:
        return redirect(url_for('purchase_orders.purchase_orders_list'))
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], po.vendor_invoice_file)        