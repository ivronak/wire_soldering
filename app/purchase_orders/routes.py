from flask import render_template, Blueprint, redirect, url_for, request, flash
from app.models import PurchaseOrder, PurchaseOrderLine, Vendor, Warehouse, RawMaterial, Unit, TaxRate
from app.extensions import db
from datetime import datetime


purchase_orders_bp = Blueprint("purchase_orders", __name__, template_folder="templates")

@purchase_orders_bp.route('/purchase_orders')
def purchase_orders_list():
    orders = PurchaseOrder.query.filter(PurchaseOrder.is_deleted == False).order_by(PurchaseOrder.id.desc()).all()
    total_count = len(orders)

    vendors = Vendor.query.filter(Vendor.is_deleted == False, Vendor.is_active == True).all()
    warehouses = Warehouse.query.filter(Warehouse.is_deleted == False, Warehouse.is_active == True).all()
    raw_materials = RawMaterial.query.filter(RawMaterial.is_deleted == False, RawMaterial.is_active == True).all()
    units = Unit.query.filter(Unit.is_active == True, Unit.is_deleted == False).all()
    tax_rates = TaxRate.query.filter(TaxRate.is_active == True, TaxRate.is_deleted == False).all()

    
    return render_template(
        "purchase_orders.html",
        active_nav='purchase_orders',
        orders=orders,
        total_count=total_count,
        result_count=total_count,
        vendors=vendors,
        warehouses=warehouses,
        raw_materials=raw_materials,
        units=units,
        tax_rates=tax_rates,
    )


@purchase_orders_bp.route('/purchase_orders/add', methods=['POST'])
def purchase_orders_add():
    vendor_id = int(request.form.get('vendor_id')) if (request.form.get('vendor_id')or "").strip() else None
    warehouse_id = int(request.form.get('warehouse_id')) if (request.form.get('warehouse_id') or "").strip() else None
    po_date_raw = (request.form.get('po_date') or "").strip()
    expected_raw = (request.form.get('expected_delivery_date') or "").strip()
    remarks = (request.form.get('remarks') or "").strip()
    payment_terms = (request.form.get('payment_terms') or "").strip()
    freight = float(request.form.get('freight')) if (request.form.get('freight') or "").strip() else 0


    if not vendor_id or not warehouse_id or not po_date_raw:
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
        payment_terms=payment_terms,
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
        discount_raw = (request.form.get(f'discount_percent_{i}') or "").strip()
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
                discount_percent=float(discount_raw) if discount_raw else 0,
            ))
        i +=1
    db.session.commit()
    flash(f"Purchase Order {po_no} saved.", "success")
    return redirect(url_for('purchase_orders.purchase_orders_list'))

