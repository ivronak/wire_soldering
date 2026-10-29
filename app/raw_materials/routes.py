from flask import render_template, Blueprint, redirect, url_for, request, flash, jsonify
from app.models import RawMaterial, RmCategories, Unit, TaxRate, RMQCParameter
from app.extensions import db

raw_materials_bp = Blueprint("raw_materials", __name__, template_folder='templates')


def generate_next_raw_material_code():
    # Auto-serial (RM-0001, RM-0002 ...) — form se code nahi aata
    last_row = RawMaterial.query.order_by(RawMaterial.id.desc()).first()
    if not last_row:
        return "RM-0001"
    next_row = last_row.id + 1
    return f"RM-{next_row:04d}"


@raw_materials_bp.route("/raw_materials")
def raw_materials_list():
    materials = RawMaterial.query.filter(RawMaterial.is_deleted == False).order_by(RawMaterial.code).all()
    total_count = len(materials)
    next_code = generate_next_raw_material_code()

    units = Unit.query.filter(Unit.is_active == True, Unit.is_deleted == False).all()
    categories = RmCategories.query.filter(RmCategories.is_active == True, RmCategories.is_deleted == False).all()
    tax_rates = TaxRate.query.filter(TaxRate.is_active == True, TaxRate.is_deleted == False).all()


    return render_template(
        "raw_materials.html",
        materials = materials,
        units = units,
        categories = categories,
        tax_rates=tax_rates,
        active_nav = 'raw_materials',
        total_count = total_count,
        result_count = total_count,
        next_code = next_code,
    )

@raw_materials_bp.route("/raw_materials/add", methods=['POST'])
def raw_materials_add():

    # Code ab auto-generated — form se code nahi aata
    code = generate_next_raw_material_code()
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
    tax_rate_id = int(request.form.get('tax_rate_id')) if (request.form.get('tax_rate_id') or "").strip() else None
    valuation_method = (request.form.get('valuation_method') or "").strip()
    is_base_metal = request.form.get('is_base_metal') == 'on'
    is_core_flux = request.form.get('is_core_flux') == 'on'
    is_packing = request.form.get('is_packing') == 'on'
    if is_packing:
        is_base_metal = is_core_flux = False          # ek hi role: packing material recipe ka metal / flux nahi

    if not name or category_id is None or base_unit_id is None:
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
            existing.tax_rate_id=tax_rate_id
            existing.valuation_method = valuation_method
            existing.is_base_metal=is_base_metal
            existing.is_core_flux=is_core_flux
            existing.is_packing=is_packing
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
        tax_rate_id=tax_rate_id,
        valuation_method=valuation_method,
        is_base_metal=is_base_metal,
        is_core_flux=is_core_flux,
        is_packing=is_packing,
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

    # Code ab auto-generated — edit pe immutable (form se code nahi aata)
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
    tax_rate_id = int(request.form.get('tax_rate_id')) if (request.form.get('tax_rate_id') or "").strip() else None
    valuation_method = (request.form.get('valuation_method') or "").strip()
    is_base_metal = request.form.get('is_base_metal') == 'on'
    is_core_flux = request.form.get('is_core_flux') == 'on'
    is_packing = request.form.get('is_packing') == 'on'
    if is_packing:
        is_base_metal = is_core_flux = False          # ek hi role: packing material recipe ka metal / flux nahi

    if not name or category_id is None or base_unit_id is None:
        return redirect(url_for('raw_materials.raw_materials_list'))

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
    m.tax_rate_id=tax_rate_id
    m.valuation_method = valuation_method
    m.is_base_metal = is_base_metal
    m.is_core_flux=is_core_flux
    m.is_packing=is_packing
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

# ---- RM QC parameters (Inward QC template) ----
# Raw Material screen ke panel se fetch() se chalte hain, isliye redirect nahi, JSON dete hain.

def qc_parameter_to_dict(p):
    return {
        "id": p.id,
        "name": p.name,
        "unit_label": p.unit_label or "",
        "check_type": p.check_type,
        "min_value": p.min_value,
        "max_value": p.max_value,
        "sort_order": p.sort_order,
    }

def read_qc_parameter_form(m, exclude_id=None):
    # Add aur Edit dono ka form padhna + validation yahin hai, do jagah copy-paste nahi.
    # Wapas deta hai: (values, None) agar sab theek, ya (None, "error message") agar galti.
    name = (request.form.get("name") or "").strip()
    unit_label = (request.form.get("unit_label") or "").strip() or None
    check_type = (request.form.get("check_type") or "range").strip()
    min_value = request.form.get("min_value", type=float)   # khaali / galat => None
    max_value = request.form.get("max_value", type=float)
    sort_order = request.form.get("sort_order", type=int) or 0

    if not name:
        return None, "Parameter name is required."
    if len(name) > 100:
        return None, "Parameter name is too long (maximum 100 characters)."
    if check_type not in ("range", "pass_fail"):
        return None, "Invalid check type."

    if check_type == "range":
        # 0 bhi sahi limit hai, isliye "is None" check
        if min_value is None and max_value is None:
            return None, "Enter a minimum, a maximum or both."
        if min_value is not None and max_value is not None and min_value > max_value:
            return None, "Minimum cannot be more than maximum."
    else:
        # pass/fail me limits ka matlab nahi, saaf kar do
        min_value = max_value = None

    # Duplicate naam: remove kiye hue ko chhod kar; edit me apni hi row ko bhi chhod kar (exclude_id)
    query = RMQCParameter.query.filter(
        RMQCParameter.raw_material_id == m.id,
        RMQCParameter.is_deleted == False,
        db.func.lower(RMQCParameter.name) == name.lower(),
    )
    if exclude_id:
        query = query.filter(RMQCParameter.id != exclude_id)
    if query.first():
        return None, "This material already has a parameter with that name."

    values = {
        "name": name,
        "unit_label": unit_label,
        "check_type": check_type,
        "min_value": min_value,
        "max_value": max_value,
        "sort_order": sort_order,
    }
    return values, None

@raw_materials_bp.route('/raw_materials/<int:m_id>/qc_parameters' )
def raw_materials_qc_parameters(m_id):
    m = RawMaterial.query.filter_by(id=m_id, is_deleted=False).first_or_404()

    params = (
        RMQCParameter.query.filter_by(raw_material_id = m_id, is_deleted=False).order_by(RMQCParameter.sort_order, RMQCParameter.id).all()
    )

    return jsonify(material=m.name, parameters=[qc_parameter_to_dict(p) for p in params])

@raw_materials_bp.route('/raw_materials/<int:m_id>/qc_parameters/add', methods=["POST"])
def raw_materials_qc_parameters_add(m_id):
    m = RawMaterial.query.filter_by(id=m_id, is_deleted=False).first_or_404()

    values, error = read_qc_parameter_form(m)

    if error:
        return jsonify(success=False, error=error)

    # Display order khaali chhoda ho (0) to naya parameter list ke AAKHIR me jode.
    # Warna 0 sabse chhota number hai aur naya parameter purano ke upar aa jata hai.
    if not values["sort_order"]:
        last_order = db.session.query(db.func.max(RMQCParameter.sort_order)).filter(
            RMQCParameter.raw_material_id == m.id,
            RMQCParameter.is_deleted == False,
        ).scalar()
        values["sort_order"] = (last_order or 0) + 1

    p = RMQCParameter(
        raw_material_id=m.id,
        **values
    )
    db.session.add(p)
    db.session.commit()
    return jsonify(success=True, parameter=qc_parameter_to_dict(p))                    

@raw_materials_bp.route('/raw_materials/<int:m_id>/qc_parameters/<int:p_id>/edit', methods=['POST'])
def raw_materials_qc_parameters_edit(m_id, p_id):

    m = RawMaterial.query.filter_by(id=m_id, is_deleted=False).first_or_404()
    p = RMQCParameter.query.filter_by(id=p_id, raw_material_id=m_id, is_deleted=False).first_or_404()

    values, error = read_qc_parameter_form(m, exclude_id=p.id)

    if error:
        return jsonify(success=False, error=error)

    p.name = values["name"]
    p.unit_label = values["unit_label"]
    p.check_type = values["check_type"]
    p.min_value = values["min_value"]
    p.max_value = values["max_value"]
    p.sort_order = values["sort_order"]
    db.session.commit()
    return jsonify(success=True, parameter=qc_parameter_to_dict(p))    

@raw_materials_bp.route("/raw_materials/<int:m_id>/qc_parameters/<int:p_id>/delete", methods=["POST"])
def raw_materials_qc_parameters_delete(m_id, p_id):
    m = RawMaterial.query.filter_by(id=m_id, is_deleted=False).first_or_404()
    p = RMQCParameter.query.filter_by(id=p_id, raw_material_id=m.id, is_deleted=False).first_or_404()

    # Soft delete: row DB me rehti hai (aage inspection results ka snapshot safe rahega)
    p.is_deleted = True
    db.session.commit()
    return jsonify(success=True)