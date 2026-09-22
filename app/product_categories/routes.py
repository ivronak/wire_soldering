from flask import render_template, Blueprint, redirect, url_for, request, flash
from app.models import ProductCategories
from app.extensions import db

product_categories_bp = Blueprint("product_categories", __name__, template_folder="templates")

@product_categories_bp.route('/product_categories')
def product_categories_list():

    categories = ProductCategories.query.filter(ProductCategories.is_deleted == False).all()
    total_count = len(categories)

    return render_template(
        "product_categories.html",
        categories=categories,
        total_count=total_count,
        result_count=total_count,
        active_nav='product_categories',
    )

@product_categories_bp.route('/product_categories/add', methods=['POST'])
def product_categories_add():
    code = (request.form.get('code') or "").strip().upper()
    name = (request.form.get('name') or "").strip()
    description = (request.form.get('description') or "").strip()

    if not code or not name:
        return redirect(url_for('product_categories.product_categories_list'))   

    existing = ProductCategories.query.filter(ProductCategories.code == code).first()
    if existing:
        if existing.is_deleted:
            existing.is_deleted = False
            existing.code = code
            existing.name = name
            existing.description = description
            existing.is_active =True

            db.session.commit()
            flash("A Product Categories restored with this code.", "success")
            return redirect(url_for('product_categories.product_categories_list'))

        flash("A Product Categories with this code already exists.", "error")   
        return redirect(url_for('product_categories.product_categories_list'))   
       

    db.session.add(ProductCategories(
        code=code,
        name=name,
        description=description,
        is_active=True,
        is_deleted=False,
    ))
    db.session.commit()
    flash("Raw Material saved.", "success")
    return redirect(url_for('product_categories.product_categories_list')) 

@product_categories_bp.route('/product_categories/toggle/<int:c_id>', methods=['POST'])
def product_categories_toggle(c_id):
    c = ProductCategories.query.get_or_404(c_id)

    c.is_active = not c.is_active
    db.session.commit()

    return redirect(url_for('product_categories.product_categories_list')) 
