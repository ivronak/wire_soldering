from flask import render_template, Blueprint, redirect, url_for, request, flash, jsonify
from app.extensions import db
from app.models import Warehouse, Branch, State

warehouses_bp = Blueprint("warehouses", __name__, template_folder="templates" )


def generate_next_warehouse_code():
    # Auto-serial (WH-0001, WH-0002 ...) — form se code nahi aata
    last_row = Warehouse.query.order_by(Warehouse.id.desc()).first()
    if not last_row:
        return "WH-0001"
    next_row = last_row.id + 1
    return f"WH-{next_row:04d}"


@warehouses_bp.route('/warehouses')
def warehouses_list():
    warehouses = Warehouse.query.filter(Warehouse.is_deleted == False).all()
    branches = Branch.query.filter(Branch.is_active == True, Branch.is_deleted == False)
    total_count = len(warehouses)
    next_code = generate_next_warehouse_code()
    return render_template(
        "warehouses.html",
        warehouses=warehouses,
        branches=branches,
        total_count=total_count,
        result_count=total_count,
        active_nav = "warehouses",
        next_code = next_code,
        # States ab State Master table se aate hain — Branch ke dropdown ke liye
        states=State.query.filter(State.is_deleted == False, State.is_active == True).order_by(State.name).all(),
    )

@warehouses_bp.route('/warehouses/branches/add', methods=['POST'])
def warehouses_branches_add():
    name = (request.form.get('name') or "").strip()
    state_id = request.form.get('state_id', type=int)
    gstin = (request.form.get('gstin') or "").strip()

    if not name:
        return jsonify(success=False, error="Branch name is required.")

    # Dropdown se aaya state_id sach me valid State hona chahiye
    if not State.query.filter(State.id == state_id, State.is_deleted == False).first():
        return jsonify(success=False, error="Please select a valid state.")

    branch = Branch(name=name, state_id=state_id, gstin=gstin or None, is_active=True, is_deleted=False)
    db.session.add(branch)
    db.session.commit()

    return jsonify(success=True, id=branch.id, name=branch.name)


@warehouses_bp.route('/warehouses/add', methods=['POST'])
def warehouses_add():
    # Code ab auto-generated — form se code nahi aata
    code = generate_next_warehouse_code()
    name = (request.form.get('name') or "").strip()
    warehouse_type = (request.form.get('warehouse_type') or "").strip()
    branch_id = int(request.form.get('branch_id')) if (request.form.get('branch_id') or "").strip() else None
    location = (request.form.get('location') or "").strip()

    if not name or not warehouse_type or not location or branch_id is None:
        return redirect(url_for('warehouses.warehouses_list'))

    # Code hamesha naya (max id + 1) banta hai, isliye normally yahan koi row nahi milti. Purana "deleted code restore"
    # wala branch kabhi chalta hi nahi tha, isliye hata diya. Sirf bachav: do log ek saath add karein to unique-code error na aaye.
    if Warehouse.query.filter_by(code=code).first():
        flash("Could not save: another warehouse was added at the same moment. Please try again.", "error")
        return redirect(url_for('warehouses.warehouses_list'))

    db.session.add(Warehouse(
        code=code,
        name=name,
        warehouse_type=warehouse_type,
        branch_id=branch_id,
        location=location,
        is_active=True,
        is_deleted=False,
    ))
    db.session.commit()
    flash("Warehouse saved.", "success")
    return redirect(url_for('warehouses.warehouses_list'))

@warehouses_bp.route('/warehouses/edit/<int:w_id>', methods=['POST'])
def warehouses_edit(w_id):
    w = Warehouse.query.get_or_404(w_id)

    # Code ab auto-generated — edit pe immutable (form se code nahi aata)
    name = (request.form.get('name') or "").strip()
    warehouse_type = (request.form.get('warehouse_type') or "").strip()
    branch_id = int(request.form.get('branch_id')) if (request.form.get('branch_id') or "").strip() else None
    location = (request.form.get('location') or "").strip()

    if not name or not warehouse_type or not location or branch_id is None:
        return redirect(url_for('warehouses.warehouses_list'))

    w.name = name
    w.warehouse_type = warehouse_type
    w.branch_id = branch_id
    w.location = location
    w.is_deleted = False

    db.session.commit()
    flash("Warehouse updated.", "success")
    return redirect(url_for('warehouses.warehouses_list'))

@warehouses_bp.route('/warehouses/toggle/<int:w_id>', methods=['POST'])
def warehouses_toggle(w_id):
    w = Warehouse.query.get_or_404(w_id)

    w.is_active = not w.is_active
    db.session.commit()
    return redirect(url_for('warehouses.warehouses_list'))
