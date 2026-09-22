from flask import Blueprint, render_template, redirect, url_for, request, flash
from app.models import Machines, WorkStage
from app.extensions import db
from datetime import date, datetime


machines_bp = Blueprint("machines",__name__, template_folder="templates")

@machines_bp.route("/machines")
def machines_list():
    if Machines.query.count() == 0:
        db.session.add(Machines(code = "MC-CUT-01", name = "Cutting Bench", work_stage_id = 1, capacity = "500 units/hr", installed_date = date(2026, 9, 19), status = "active",))
        db.session.commit()

    machines = (
        Machines.query.filter(Machines.is_deleted == False).order_by(Machines.code).all()
    )

    total_count = len(machines)

    stages = WorkStage.query.filter(WorkStage.is_active == True, WorkStage.is_deleted == False).order_by(WorkStage.sort_order).all()


    return render_template(
        "machines.html",
        machines=machines,
        total_count=total_count,
        active_nav="machines",
        result_count=total_count,
        stages=stages,
    )


@machines_bp.route("/machines/add", methods=['POST'])
def machines_add():
    code = (request.form.get('code') or "").strip().upper()
    name = (request.form.get('name') or "").strip()
    work_stage_id = int(request.form.get('work_stage_id')) or None
    capacity = (request.form.get('capacity') or "").strip() or None
    status = (request.form.get('status') or "active").strip().lower()
    raw_date = (request.form.get('installed_date') or "").strip()
    installed_date = datetime.strptime(raw_date, "%Y-%m-%d").date() if raw_date else None

    if not code or not name or not work_stage_id:
        return redirect(url_for('machines.machines_list'))

    work_stage = WorkStage.query.get_or_404(work_stage_id)

    existing = Machines.query.filter_by(code=code).first()
    if existing:
        if existing.is_deleted:
            existing.is_deleted = False
            existing.name = name
            existing.work_stage_id = work_stage_id
            existing.capacity =  capacity
            existing.installed_date = installed_date
            existing.status =  status
            db.session.commit()
            flash("Machine restored with this code.","success")
            return redirect(url_for('machines.machines_list'))
        flash("A machine with this code already exists.","error")    
        return redirect(url_for('machines.machines_list'))

    db.session.add(Machines(
        code=code,
        name=name,
        work_stage_id=work_stage_id,
        capacity=capacity,
        installed_date=installed_date,
        status=status,
        is_deleted=False,
    ))        
    db.session.commit()
    flash("Machine saved.", "success")
    return redirect(url_for('machines.machines_list'))
    
@machines_bp.route("/machines/status/<int:machine_id>", methods=["POST"])
def machines_status(machine_id):
    m = Machines.query.get_or_404(machine_id)
    status = (request.form.get('status') or "").strip().lower()
    allowed = ["active", "maintenance", "breakdown", "retired"]

    if status in allowed:
        m.status = status
        db.session.commit()
    return redirect(url_for('machines.machines_list'))    

@machines_bp.route("/machines/edit/<int:machine_id>", methods=['POST'])
def machines_edit(machine_id):
    m = Machines.query.get_or_404(machine_id)

    code = (request.form.get('code') or "").strip().upper()
    name = (request.form.get('name') or "").strip()
    work_stage_id = int(request.form.get('work_stage_id')) or None
    capacity = (request.form.get('capacity') or "").strip() or None
    status = (request.form.get('status') or "active").strip().lower()
    raw_date = (request.form.get('installed_date') or "").strip()
    installed_date = datetime.strptime(raw_date, "%Y-%m-%d").date() if raw_date else None

    if not code or not name or not work_stage_id:
        return redirect(url_for('machines.machines_list'))

    dup = Machines.query.filter(Machines.code == code, Machines.id != machine_id).first()
    if dup:
        flash("A machine with this code already exists.", "error")
        return redirect(url_for('machines.machines_list'))

    work_stage = WorkStage.query.get_or_404(work_stage_id)

    m.code = code
    m.name = name
    m.work_stage_id = work_stage_id
    m.capacity = capacity
    m.status = status
    m.installed_date = installed_date
    db.session.commit()
    flash("Machine updated.", "success")
    return redirect(url_for('machines.machines_list'))

@machines_bp.route('/machines/delete/<int:machine_id>', methods=['POST'])
def machines_delete(machine_id):
    m = Machines.query.get_or_404(machine_id)

    m.is_deleted = True
    db.session.commit()
    flash("Machine removed from the list (kept in database).", "success")

    return redirect(url_for('machines.machines_list'))