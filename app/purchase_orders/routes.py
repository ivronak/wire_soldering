from flask import render_template, Blueprint, redirect, url_for, request, flash
from app.models import PurchaseOrder, PurchaseOrderLine, Vendor, Warehouse, RawMaterial
from app.extensions import db

purchase_orders_bp = Blueprint("purchase_orders", __name__, template_folder="templates")

@purchase_orders_bp.route('/purchase_orders')
def purchase_orders_list():
    orders = PurchaseOrder.query.filter(PurchaseOrder.is_deleted == False).order_by(PurchaseOrder.id.desc()).all()
    total_count = len(orders)

    vendors = Vendor.query.filter(Vendor.is_deleted == False, Vendor.is_active == True).all()
    warehouses = Warehouse.query.filter(Warehouse.is_deleted == False, Warehouse.is_active == True).all()
    raw_materials = RawMaterial.query.filter(RawMaterial.is_deleted == False, RawMaterial.is_active == True).all()
    
    return render_template(
        "purchase_orders.html",
        active_nav='purchase_orders',
        orders=orders,
        total_count=total_count,
        result_count=total_count,
        vendors=vendors,
        warehouses=warehouses,
        raw_materials=raw_materials,
    )



