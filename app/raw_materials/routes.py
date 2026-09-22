from flask import render_template, Blueprint, redirect, url_for, request, flash
from app.models import RawMaterial, RmCategories, Unit
from app.extensions import db

raw_materials_bp = Blueprint("raw_materials", __name__, template_folder='templates')

@raw_materials_bp.route("/raw_materials")
def raw_materials_list():
    materials = RawMaterial.query.filter(RawMaterial.is_deleted == False).order_by(RawMaterial.code).all()
    total_count = len(materials)

    units = Unit.query.filter(Unit.is_active == True, Unit.is_deleted == False).all()
    categories = RmCategories.query.filter(RmCategories.is_active == True, RmCategories.is_deleted == False).all()

    return render_template(
        "raw_materials.html",
        materials = materials,
        units = units,
        categories = categories,
        active_nav = 'raw_materials',
        total_count = total_count,
        result_count = total_count,
    )

@raw_materials_bp.route("/raw_materials/add", methods=['POST'])
def raw_materials_add():

    code = (request.form.get('code') or "").strip().upper()
    name = (request.form.get('name') or "").strip()
    description = (request.form.get('description') or "").strip()
    category_id = int(request.form.get('category_id')) if (request.form.get('category_id') or "").strip() else None
    base_unit_id = int(request.form.get('base_unit_id')) if (request.form.get('base_unit_id') or "").strip() else None
    alt_unit_id = int(request.form.get('alt_unit_id')) if (request.form.get('alt_unit_id') or "").strip() else None
    conversion_note = (request.form.get('conversion_note') or "").strip()
    reorder_level = int(request.form.get('reorder_level')) if (request.form.get('reorder_level') or "").strip() else None
    min_stock = int(request.form.get('min_stock')) if (request.form.get('min_stock') or "").strip() else None
    max_stock = int(request.form.get('max_stock')) if (request.form.get('max_stock') or "").strip() else None
    hsn_code = (request.form.get('hsn_code') or "").strip()
    valuation_method = (request.form.get('valuation_method') or "").strip()

    if not code or not name or category_id is None or base_unit_id is None:
        return redirect(url_for('raw_materials.raw_materials_list'))

    existing = RawMaterial.query.filter_by(code=code).first()
    if existing :
        if existing.is_deleted:
            existing.is_deleted = False
            existing.name = name
            existing.description = description
            existing.category_id = category_id
            existing.base_unit_id = base_unit_id
            existing.alt_unit_id = alt_unit_id
            existing.conversion_note = conversion_note
            existing.reorder_level = reorder_level
            existing.min_stock = min_stock
            existing.max_stock = max_stock
            existing.hsn_code = hsn_code
            existing.valuation_method = valuation_method
            existing.is_active = True
            db.session.commit()
            flash("A Raw Material restored with this code.", "success")
            return redirect(url_for('raw_materials.raw_materials_list'))

        flash("A Raw Material with this code already exists.", "error")   
        return redirect(url_for('raw_materials.raw_materials_list'))     


    db.session.add(RawMaterial(
        code=code,
        name=name,
        description=description,
        category_id=category_id,
        base_unit_id=base_unit_id,
        alt_unit_id=alt_unit_id,
        conversion_note=conversion_note,
        reorder_level=reorder_level,
        min_stock=min_stock,
        max_stock=max_stock,
        hsn_code=hsn_code,
        valuation_method=valuation_method,
        is_active=True,
        is_deleted=False,
    ))

    db.session.commit()
    flash("Raw Material saved.", "success")

    return redirect(url_for('raw_materials.raw_materials_list'))

@raw_materials_bp.route('/raw_materials/toggle/<int:m_id>', methods=['POST'])
def raw_materials_toggle(m_id):
    m = RawMaterial.query.get_or_404(m_id)

    m.is_active = not m.is_active
    db.session.commit()

    return redirect(url_for('raw_materials.raw_materials_list'))

@raw_materials_bp.route('/raw_materials/edit/<int:m_id>', methods=['POST'])
def raw_materials_edit(m_id):
    m = RawMaterial.query.get_or_404(m_id)

    code = (request.form.get('code') or "").strip().upper()
    name = (request.form.get('name') or "").strip()
    description = (request.form.get('description') or "").strip()
    category_id = int(request.form.get('category_id')) if (request.form.get('category_id') or "").strip() else None
    base_unit_id = int(request.form.get('base_unit_id')) if (request.form.get('base_unit_id') or "").strip() else None
    alt_unit_id = int(request.form.get('alt_unit_id')) if (request.form.get('alt_unit_id') or "").strip() else None
    conversion_note = (request.form.get('conversion_note') or "").strip()
    reorder_level = int(request.form.get('reorder_level')) if (request.form.get('reorder_level') or "").strip() else None
    min_stock = int(request.form.get('min_stock')) if (request.form.get('min_stock') or "").strip() else None
    max_stock = int(request.form.get('max_stock')) if (request.form.get('max_stock') or "").strip() else None
    hsn_code = (request.form.get('hsn_code') or "").strip()
    valuation_method = (request.form.get('valuation_method') or "").strip()

    if not code or not name or category_id is None or base_unit_id is None:
        return redirect(url_for('raw_materials.raw_materials_list'))

    dup = RawMaterial.query.filter(RawMaterial.code == code, RawMaterial.id != m_id).first()
    if dup:
        flash("A Raw Material with this code already exists.", "error")   
        return redirect(url_for('raw_materials.raw_materials_list'))

    m.code = code
    m.name = name
    m.description = description
    m.category_id = category_id
    m.base_unit_id = base_unit_id
    m.alt_unit_id = alt_unit_id
    m.conversion_note = conversion_note
    m.reorder_level = reorder_level
    m.min_stock = min_stock
    m.max_stock = max_stock
    m.hsn_code = hsn_code
    m.valuation_method = valuation_method
    m.is_deleted = False

    db.session.commit()
    flash("Raw Material updated.", "success")    
    return redirect(url_for('raw_materials.raw_materials_list'))

@raw_materials_bp.route('/raw_materials/delete/<int:m_id>', methods=['POST'])
def raw_materials_delete(m_id):
    m = RawMaterial.query.get_or_404(m_id)

    m.is_deleted = True
    db.session.commit()
    flash("Raw Material removed from the list (kept in database).", "success")
    return redirect(url_for('raw_materials.raw_materials_list'))
