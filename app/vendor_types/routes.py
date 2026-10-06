from flask import render_template, Blueprint, url_for, redirect, request, flash
from app.models import VendorType
from app.extensions import db

vendor_types_bp = Blueprint("vendor_types", __name__, template_folder="templates")


def generate_next_vendor_type_code():
    # Charges / State jaisa hi simple auto-serial code (VT-0001, VT-0002 ...)
    last_row = VendorType.query.order_by(VendorType.id.desc()).first()
    if not last_row:
        return "VT-0001"

    next_row = last_row.id + 1
    return f"VT-{next_row:04d}"


@vendor_types_bp.route('/vendor_types')
def vendor_types_list():
    vendor_types = VendorType.query.filter(VendorType.is_deleted == False).order_by(VendorType.code).all()
    total_count = len(vendor_types)
    next_code = generate_next_vendor_type_code()

    return render_template(
        "vendor_types.html",
        vendor_types=vendor_types,
        next_code=next_code,
        total_count=total_count,
        result_count=total_count,
        active_nav='vendor_types',
    )


@vendor_types_bp.route('/vendor_types/add', methods=['POST'])
def vendor_types_add():

    code = generate_next_vendor_type_code()
    name = (request.form.get('name') or "").strip()

    if not code or not name:
        return redirect(url_for('vendor_types.vendor_types_list'))

    existing = VendorType.query.filter_by(code=code).first()
    if existing:
        if existing.is_deleted:
            # Isi code pe soft-deleted row mili — usko restore karo (Charges jaisa)
            existing.is_deleted = False
            existing.code = code
            existing.name = name
            existing.is_active = True
            db.session.commit()
            flash("A Vendor type restored with this code.", "success")
            return redirect(url_for('vendor_types.vendor_types_list'))

        flash("A Vendor type with this code already exists.", "error")
        return redirect(url_for('vendor_types.vendor_types_list'))

    db.session.add(VendorType(
        code=code,
        name=name,
        is_active=True,
        is_deleted=False,
    ))
    db.session.commit()
    flash("Vendor type saved.", "success")
    return redirect(url_for('vendor_types.vendor_types_list'))


@vendor_types_bp.route('/vendor_types/delete/<int:vt_id>', methods=['POST'])
def vendor_types_delete(vt_id):
    vt = VendorType.query.get_or_404(vt_id)

    vt.is_deleted = True
    db.session.commit()
    flash("Vendor type removed from the list (kept in database).", "success")
    return redirect(url_for('vendor_types.vendor_types_list'))


@vendor_types_bp.route('/vendor_types/toggle/<int:vt_id>', methods=['POST'])
def vendor_types_toggle(vt_id):
    vt = VendorType.query.get_or_404(vt_id)

    vt.is_active = not vt.is_active
    db.session.commit()
    return redirect(url_for('vendor_types.vendor_types_list'))


@vendor_types_bp.route('/vendor_types/edit/<int:vt_id>', methods=['POST'])
def vendor_types_edit(vt_id):
    vt = VendorType.query.get_or_404(vt_id)
    # .get() ke bina, name field missing ho to None.strip() crash karta tha
    name = (request.form.get('name') or "").strip()

    if not name:
        return redirect(url_for('vendor_types.vendor_types_list'))

    vt.name = name
    db.session.commit()
    flash("Vendor type Updated.", "success")
    return redirect(url_for('vendor_types.vendor_types_list'))
