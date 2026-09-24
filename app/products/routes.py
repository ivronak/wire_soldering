from flask import render_template, Blueprint, redirect, url_for, request, flash
from app.models import Product, ProductCategories, Unit, TaxRate
from app.extensions import db

products_bp = Blueprint("products", __name__, template_folder="templates")

@products_bp.route("/products")
def products_list():

    products = Product.query.filter(Product.is_deleted == False).order_by(Product.code).all()
    total_count = len(products)

    units = Unit.query.filter(Unit.is_deleted == False, Unit.is_active == True).all()
    categories = ProductCategories.query.filter(ProductCategories.is_deleted == False,              ProductCategories.is_active == True).all()
    tax_rates = TaxRate.query.filter(TaxRate.is_active == True, TaxRate.is_deleted == False).order_by(TaxRate.code).all()

    return render_template(
        "products.html",
        active_nav='products',
        products=products,
        total_count=total_count,
        result_count=total_count,
        categories=categories,
        units=units,
        tax_rates=tax_rates,
    )

@products_bp.route("/products/add", methods=['POST'])
def products_add():
    code = (request.form.get('code') or "").strip().upper()
    name = (request.form.get('name') or "").strip()
    category_id = int(request.form.get('category_id')) if (request.form.get('category_id') or "").strip() else None
    description = (request.form.get('description') or "").strip()
    base_unit_id = int(request.form.get('base_unit_id')) if (request.form.get('base_unit_id') or "").strip() else None
    hsn_code = (request.form.get('hsn_code') or "").strip()
    tax_rate_id = int(request.form.get('tax_rate_id')) if (request.form.get('tax_rate_id') or "").strip() else None

    if not code or not name or category_id is None or base_unit_id is None or tax_rate_id is None:
        return redirect(url_for('products.products_list'))

    existing = Product.query.filter(Product.code == code).first()
    if existing:
        if existing.is_deleted:
            existing.is_deleted = False
            existing.code = code
            existing.name = name
            existing.description = description
            existing.category_id = category_id
            existing.base_unit_id = base_unit_id
            existing.tax_rate_id = tax_rate_id
            existing.hsn_code = hsn_code
            existing.is_active = True
            db.session.commit()
            flash("A Product restored with this code.", "success")    
            return redirect(url_for('products.products_list'))

        flash("A Product with this code already exists.", "error")    
        return redirect(url_for('products.products_list'))

    db.session.add(Product(
        code=code,
        name=name,
        description=description,
        category_id=category_id,
        base_unit_id=base_unit_id,
        tax_rate_id=tax_rate_id,
        hsn_code=hsn_code,
        is_active=True,
        is_deleted=False,
    ))    
    db.session.commit()
    flash("Product saved.", "success")

    return redirect(url_for('products.products_list'))

@products_bp.route('/products/toggle/<int:p_id>', methods=['POST'])
def products_toggle(p_id):
    p = Product.query.get_or_404(p_id)

    p.is_active = not p.is_active
    db.session.commit()
    return redirect(url_for('products.products_list'))     

@products_bp.route('/products/edit/<int:p_id>', methods=['POST'])
def products_edit(p_id):
    p = Product.query.get_or_404(p_id)

    code = (request.form.get('code') or "").strip().upper()
    name = (request.form.get('name') or "").strip()
    category_id = int(request.form.get('category_id')) if (request.form.get('category_id') or "").strip() else None
    description = (request.form.get('description') or "").strip()
    base_unit_id = int(request.form.get('base_unit_id')) if (request.form.get('base_unit_id') or "").strip() else None
    hsn_code = (request.form.get('hsn_code') or "").strip()
    tax_rate_id = int(request.form.get('tax_rate_id')) if (request.form.get('tax_rate_id') or "").strip() else None

    if not code or not name or category_id is None or base_unit_id is None or tax_rate_id is None:
        return redirect(url_for('products.products_list'))

    dup = Product.query.filter(Product.code == code, Product.id != p_id).first()
    if dup:
        flash("A Product with this code already exists.", "error") 
        return redirect(url_for('products.products_list'))

    p.code = code
    p.name = name
    p.description = description
    p.category_id = category_id
    p.base_unit_id = base_unit_id
    p.tax_rate_id = tax_rate_id
    p.hsn_code = hsn_code
    p.is_deleted = False

    db.session.commit()
    flash("Product updated.", "success")   
    return redirect(url_for('products.products_list'))

@products_bp.route('/products/delete/<int:p_id>', methods=['POST'])
def products_delete(p_id):
    p = Product.query.get_or_404(p_id)

    p.is_deleted = True
    db.session.commit()

    flash("Product removed from the list (kept in database).", "success")
    return redirect(url_for('products.products_list'))

