from flask import render_template, Blueprint, redirect, url_for, request, flash
from app.models import ProductCategories
from app.extensions import db

product_categories_bp = Blueprint("product_categories", __name__, template_folder="templates")


def generate_next_product_category_code():
    # Auto-serial (PC-0001, PC-0002 ...) — form se code nahi aata
    last_row = ProductCategories.query.order_by(ProductCategories.id.desc()).first()
    if not last_row:
        return "PC-0001"
    next_row = last_row.id + 1
    return f"PC-{next_row:04d}"


def read_attributes_fields():
    names = []
    seen = set()
    for raw in request.form.getlist('attr_field[]'):
        name = (raw or "").strip()
        key = name.lower()
        if not name or key in seen:
            continue
        seen.add(key)
        names.append(name)
    return names


@product_categories_bp.route('/product_categories')
def product_categories_list():

    categories = ProductCategories.query.filter(ProductCategories.is_deleted == False).all()
    total_count = len(categories)
    next_code = generate_next_product_category_code()

    return render_template(
        "product_categories.html",
        categories=categories,
        total_count=total_count,
        result_count=total_count,
        active_nav='product_categories',
        next_code=next_code,
    )


@product_categories_bp.route('/product_categories/add', methods=['POST'])
def product_categories_add():
    # Code ab auto-generated — form se code nahi aata
    code = generate_next_product_category_code()
    name = (request.form.get('name') or "").strip()
    description = (request.form.get('description') or "").strip()

    if not name:
        return redirect(url_for('product_categories.product_categories_list'))

    existing = ProductCategories.query.filter(ProductCategories.code == code).first()
    if existing:
        if existing.is_deleted:
            existing.is_deleted = False
            existing.code = code
            existing.name = name
            existing.description = description
            existing.attribute_fields = read_attributes_fields()
            existing.is_active = True

            db.session.commit()
            flash("A Product Category restored with this code.", "success")
            return redirect(url_for('product_categories.product_categories_list'))

        flash("A Product Category with this code already exists.", "error")
        return redirect(url_for('product_categories.product_categories_list'))

    db.session.add(ProductCategories(
        code=code,
        name=name,
        description=description,
        attribute_fields=read_attributes_fields(),
        is_active=True,
        is_deleted=False,
    ))
    db.session.commit()
    flash("Product Category saved.", "success")
    return redirect(url_for('product_categories.product_categories_list'))


@product_categories_bp.route('/product_categories/toggle/<int:c_id>', methods=['POST'])
def product_categories_toggle(c_id):
    c = ProductCategories.query.get_or_404(c_id)

    c.is_active = not c.is_active
    db.session.commit()

    return redirect(url_for('product_categories.product_categories_list'))


@product_categories_bp.route('/product_categories/edit/<int:c_id>', methods=['POST'])
def product_categories_edit(c_id):
    c = ProductCategories.query.get_or_404(c_id)

    # Code ab auto-generated — edit pe immutable (form se code nahi aata)
    name = (request.form.get('name') or "").strip()
    description = (request.form.get('description') or "").strip()

    if not name:
        return redirect(url_for('product_categories.product_categories_list'))

    c.name = name
    c.description = description
    c.attribute_fields = read_attributes_fields()
    c.is_deleted = False

    db.session.commit()
    flash("Product Category updated.", "success")
    return redirect(url_for('product_categories.product_categories_list'))


@product_categories_bp.route('/product_categories/delete/<int:c_id>', methods=['POST'])
def product_categories_delete(c_id):
    c = ProductCategories.query.get_or_404(c_id)

    c.is_deleted = True
    db.session.commit()
    flash("Product Category removed from the list (kept in database).", "success")
    return redirect(url_for('product_categories.product_categories_list'))
