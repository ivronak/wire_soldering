from flask import render_template, Blueprint, redirect, url_for, request, flash, jsonify
from app.extensions import db
from app.models import Warehouse, Branch

warehouses_bp = Blueprint("warehouses", __name__, template_folder="templates" )

@warehouses_bp.route('/warehouses')
def warehouses_list():
    warehouses = Warehouse.query.filter(Warehouse.is_deleted == False).all()
    branches = Branch.query.filter(Branch.is_active == True, Branch.is_deleted == False)
    total_count = len(warehouses)
    return render_template(
        "warehouses.html",
        warehouses=warehouses,
        branches=branches,
        total_count=total_count,
        result_count=total_count,
        active_nav = "warehouses",
    )

@warehouses_bp.route('/warehouses/branches/add', methods=['POST'])
def warehouses_branches_add():
    name = (request.form.get('name') or "").strip()
    state = (request.form.get('state') or "").strip()
    gstin = (request.form.get('gstin') or "").strip()

    if not name: 
        return jsonify(success=False, error="Branch name is required.")

    branch = Branch( name=name, state=state or None, gstin=gstin or None, is_active=True, is_deleted=False)    
    db.session.add(branch)
    db.session.commit()

    return jsonify(success=True, id=branch.id, name=branch.name)


@warehouses_bp.route('/warehouses/add', methods=['POST'])
def warehouses_add():
    code = (request.form.get('code') or "").strip().upper()
    name = (request.form.get('name') or "").strip()
    warehouse_type = (request.form.get('warehouse_type') or "").strip()
    branch_id = int(request.form.get('branch_id')) if (request.form.get('branch_id') or "").strip() else None
    location = (request.form.get('location') or "").strip()

    if not code or not name or not warehouse_type or not location or branch_id is None:
        return redirect(url_for('warehouses.warehouses_list'))

    existing = Warehouse.query.filter_by(code=code).first()
    if existing:
        if existing.is_deleted:
            existing.is_deleted = False
            existing.code = code
            existing.name = name
            existing.warehouse_type = warehouse_type
            existing.branch_id = branch_id
            existing.location = location
            existing.is_active = True
            db.session.commit()
            flash("A Warehouse restored with this code.", "success")
            return redirect(url_for('warehouses.warehouses_list'))

        flash("A Warehouse with this code already exists.", "error")    
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

    code = (request.form.get('code') or "").strip().upper()
    name = (request.form.get('name') or "").strip()
    warehouse_type = (request.form.get('warehouse_type') or "").strip()
    branch_id = int(request.form.get('branch_id')) if (request.form.get('branch_id') or "").strip() else None
    location = (request.form.get('location') or "").strip()

    if not code or not name or not warehouse_type or not location or branch_id is None:
        return redirect(url_for('warehouses.warehouses_list'))

    dup = Warehouse.query.filter(Warehouse.code == code, Warehouse.id != w_id).first()
    if dup:
        flash("A Warehouse with this code already exists.", "error")
        return redirect(url_for('warehouses.warehouses_list'))

    w.code = code
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

