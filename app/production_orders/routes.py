# Production order: product choose karo, qty do, uski recipe is document pe copy ho jati hai.
# Baad mein product recipe badlegi to purana order nahi badlega.
import os
from werkzeug.utils import secure_filename
from datetime import datetime
from flask import Blueprint, flash, redirect, render_template, request, url_for
from app.extensions import db
from app.models import Product, ProductCategories, ProductionOrder, ProductionOrderLine, RawMaterial

production_orders_bp = Blueprint("production_orders", __name__, template_folder="templates")


def _planner_products():
    products = (
        Product.query.filter(Product.is_deleted == False, Product.is_active == True)
        .order_by(Product.code)
        .all()
    )
    planner = []
    for p in products:
        lines = []
        for r in p.recipe_items:
            rm = r.raw_material
            lines.append({
                "rm_id": r.raw_material_id,
                "code": rm.code if rm else "",
                "name": rm.name if rm else "",
                "unit": rm.base_unit.code if rm and rm.base_unit else "",
                "ratio": r.ratio_percent,
                "is_flux": bool(r.is_flux),
            })
        planner.append({
            "id": p.id,
            "code": p.code,
            "name": p.name,
            "category_id": p.category_id,
            "unit": p.base_unit.code if p.base_unit else "KG",
            "attributes": p.attributes or {},
            "recipe": lines,
        })
    return products, planner


@production_orders_bp.route("/production_orders")
def production_orders_list():
    orders = (
        ProductionOrder.query.filter(ProductionOrder.is_deleted == False)
        .order_by(ProductionOrder.id.desc())
        .all()
    )
    products, planner = _planner_products()
    categories = (
        ProductCategories.query.filter(
            ProductCategories.is_deleted == False,
            ProductCategories.is_active == True,
        )
        .order_by(ProductCategories.name)
        .all()
    )
    raw_materials = (
        RawMaterial.query.filter(RawMaterial.is_deleted == False, RawMaterial.is_active == True)
        .order_by(RawMaterial.code)
        .all()
    )
    material_options = [{
        "id": rm.id,
        "code": rm.code,
        "name": rm.name,
        "unit": rm.base_unit.code if rm.base_unit else "",
    } for rm in raw_materials]
    return render_template(
        "production_orders.html",
        active_nav="production_orders",
        orders=orders,
        total_count=len(orders),
        result_count=len(orders),
        products=products,
        categories=categories,
        planner=planner,
        material_options=material_options,
    )


@production_orders_bp.route("/production_orders/add", methods=["POST"])
def production_orders_add():
    product_id = int(request.form.get("product_id")) if (request.form.get("product_id") or "").strip() else None
    date_raw = (request.form.get("order_date") or "").strip()
    qty_raw = (request.form.get("planned_qty") or "").strip()
    weight_raw = (request.form.get("unit_weight") or "").strip()
    remarks = (request.form.get("remarks") or "").strip()

    product = Product.query.get(product_id) if product_id else None
    if not product or product.is_deleted or not product.is_active:
        flash("Choose an active product.", "error")
        return redirect(url_for("production_orders.production_orders_list"))
    if not date_raw or not qty_raw:
        flash("Date and quantity are required.", "error")
        return redirect(url_for("production_orders.production_orders_list"))
    if not product.recipe_items:
        flash("This product has no recipe, so a production order cannot be created.", "error")
        return redirect(url_for("production_orders.production_orders_list"))

    try:
        order_date = datetime.strptime(date_raw, "%Y-%m-%d").date()
        planned_qty = float(qty_raw)
    except ValueError:
        flash("Date or quantity is not valid.", "error")
        return redirect(url_for("production_orders.production_orders_list"))
    if planned_qty <= 0:
        flash("Quantity must be greater than zero.", "error")
        return redirect(url_for("production_orders.production_orders_list"))

    unit_code = (product.base_unit.code if product.base_unit else "KG").upper()
    is_kg = unit_code in ("KG", "KGS")
    if is_kg:
        unit_weight = 1.0
    else:
        try:
            unit_weight = float(weight_raw)
        except ValueError:
            unit_weight = 0
        if unit_weight <= 0:
            flash("Enter the weight per unit in KG.", "error")
            return redirect(url_for("production_orders.production_orders_list"))

    batch_kg = planned_qty * unit_weight
    year = order_date.year
    count = ProductionOrder.query.filter(ProductionOrder.prod_no.like(f"PROD-{year}-%")).count()
    prod_no = f"PROD-{year}-{count + 1:03d}"

    order = ProductionOrder(
        prod_no=prod_no,
        product_id=product.id,
        order_date=order_date,
        planned_qty=planned_qty,
        unit_weight=unit_weight,
        status="Draft",
        remarks=remarks,
        is_deleted=False,
    )
    db.session.add(order)
    db.session.flush()

    # Master recipe ki id save nahi karte. Ratio aur qty is order pe copy.
    for r in product.recipe_items:
        db.session.add(ProductionOrderLine(
            production_order_id=order.id,
            raw_material_id=r.raw_material_id,
            ratio_percent=r.ratio_percent,
            required_qty=batch_kg * (r.ratio_percent or 0) / 100,
            is_flux=bool(r.is_flux),
            is_extra=False,
        ))

    # Packaging / extra RM recipe ka percent nahi. User jo qty type kare wahi save.
    extra_ids = request.form.getlist("extra_rm_id[]")
    extra_qtys = request.form.getlist("extra_qty[]")
    seen_extra = set()
    for rm_raw, qty_raw in zip(extra_ids, extra_qtys):
        rm_raw = (rm_raw or "").strip()
        qty_raw = (qty_raw or "").strip()
        if not rm_raw and not qty_raw:
            continue
        if not rm_raw or not qty_raw:
            db.session.rollback()
            flash("Each added material needs a raw material and a quantity.", "error")
            return redirect(url_for("production_orders.production_orders_list"))
        try:
            rm_id = int(rm_raw)
            extra_qty = float(qty_raw)
        except ValueError:
            db.session.rollback()
            flash("An added material line is not valid.", "error")
            return redirect(url_for("production_orders.production_orders_list"))
        if extra_qty <= 0:
            db.session.rollback()
            flash("Added material quantity must be greater than zero.", "error")
            return redirect(url_for("production_orders.production_orders_list"))
        if rm_id in seen_extra:
            db.session.rollback()
            flash("The same extra material is added twice. Keep one line and change its quantity.", "error")
            return redirect(url_for("production_orders.production_orders_list"))
        rm = RawMaterial.query.get(rm_id)
        if not rm or rm.is_deleted or not rm.is_active:
            db.session.rollback()
            flash("Choose an active raw material for the added line.", "error")
            return redirect(url_for("production_orders.production_orders_list"))
        seen_extra.add(rm_id)
        db.session.add(ProductionOrderLine(
            production_order_id=order.id,
            raw_material_id=rm.id,
            ratio_percent=0,
            required_qty=extra_qty,
            is_flux=False,
            is_extra=True,
        ))

    db.session.commit()
    flash(f"Production order {order.prod_no} saved.", "success")
    return redirect(url_for("production_orders.production_orders_list"))
