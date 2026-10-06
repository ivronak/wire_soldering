from flask import render_template, Blueprint, request, redirect, url_for, flash
from app.models import RmCategories
from app.extensions import db

rm_categories_bp = Blueprint("rm_categories", __name__, template_folder='templates')


def generate_next_rm_category_code():
    # Auto-serial (RMC-0001, RMC-0002 ...) — form se code nahi aata
    last_row = RmCategories.query.order_by(RmCategories.id.desc()).first()
    if not last_row:
        return "RMC-0001"
    next_row = last_row.id + 1
    return f"RMC-{next_row:04d}"


@rm_categories_bp.route('/rm_categories')
def rm_categories_list():
    if RmCategories.query.count() == 0:
        db.session.add(RmCategories(
            code="RMC-0001",
            name="Metal",
            description="the metal materials used as raw materials in production.",
            is_active=True,
            is_deleted=False,
        ))
        db.session.commit()

    categories = RmCategories.query.filter(RmCategories.is_deleted == False).order_by(RmCategories.code).all()
    total_count = len(categories)
    next_code = generate_next_rm_category_code()
    return render_template(
        'rm_categories.html',
        categories=categories,
        active_nav='rm_categories',
        total_count=total_count,
        result_count=total_count,
        next_code=next_code,
    )
@rm_categories_bp.route('/rm_categories/add', methods=['POST'])
def rm_categories_add():
    code = generate_next_rm_category_code()
    name = (request.form.get('name') or "").strip()
    description = (request.form.get('description') or "").strip()

    if not name:
        return redirect(url_for('rm_categories.rm_categories_list'))

    existing = RmCategories.query.filter_by(code=code).first()
    if existing:
        if existing.is_deleted:
            existing.is_deleted = False
            existing.code = code
            existing.name = name
            existing.description = description
            existing.is_active = True
            db.session.commit()
            flash("A RM Category restored with this code.", "success")
            return redirect(url_for('rm_categories.rm_categories_list'))

        flash("A RM Category with this code already exists.", "error")
        return redirect(url_for('rm_categories.rm_categories_list'))

    db.session.add(RmCategories(
        code=code,
        name=name,
        description=description,
        is_active=True,
        is_deleted=False,
    ))
    db.session.commit()

    flash("RM Category saved.", "success")
    return redirect(url_for('rm_categories.rm_categories_list'))


@rm_categories_bp.route('/rm_categories/toggle/<int:c_id>', methods=['POST'])
def rm_categories_toggle(c_id):
    c = RmCategories.query.get_or_404(c_id)
    
    c.is_active = not c.is_active
    db.session.commit()
    return redirect(url_for('rm_categories.rm_categories_list'))

@rm_categories_bp.route('/rm_categories/edit/<int:c_id>', methods=['POST'])
def rm_categories_edit(c_id):
    c = RmCategories.query.get_or_404(c_id)

    # Code ab auto-generated — edit pe immutable (form se code nahi aata)
    name = (request.form.get('name') or "").strip()
    description = (request.form.get('description') or "").strip()

    if not name:
        return redirect(url_for('rm_categories.rm_categories_list'))

    c.name = name
    c.description = description
    c.is_active = True
    c.is_deleted = False

    db.session.commit()
    flash("RM Category updated.", "success")
    return redirect(url_for('rm_categories.rm_categories_list'))

@rm_categories_bp.route('/rm_categories/delete/<int:c_id>', methods=['POST'])
def rm_categories_delete(c_id):
    c = RmCategories.query.get_or_404(c_id) 

    c.is_deleted = True
    db.session.commit()
    flash("RM Category removed from the list (kept in database).", "success")     
    return redirect(url_for('rm_categories.rm_categories_list'))     