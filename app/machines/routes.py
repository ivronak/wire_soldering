from flask import Blueprint, render_template, redirect, url_for, request, flash
from app.models import Machines, WorkStage, Unit, ProductionLine
from app.extensions import db
from datetime import datetime


machines_bp = Blueprint("machines",__name__, template_folder="templates")

def generate_next_machine_code():
    # Auto-serial (MC-0001, MC-0002 ...) — form se code nahi aata
    last_row = Machines.query.order_by(Machines.id.desc()).first()
    if not last_row:
        return "MC-0001"
    next_row = last_row.id + 1
    return f"MC-{next_row:04d}"

@machines_bp.route("/machines")
def machines_list():
    # Pehle yahan khaali table pe ek demo machine (work_stage_id=1 fixed) apne aap ban jaati thi —
    # hata diya: master data hamesha user UI se daale, code me hardcode nahi (CLAUDE.md §5 rule 1),
    # aur id=1 wali work stage exist na kare to machine galat stage se jud jaati.
    machines = (
        Machines.query.filter(Machines.is_deleted == False).order_by(Machines.code).all()
    )
    total_count = len(machines)
    stages = WorkStage.query.filter(WorkStage.is_active == True, WorkStage.is_deleted == False).order_by(WorkStage.sort_order).all()
    next_code = generate_next_machine_code()

    return render_template(
        "machines.html",
        machines=machines,
        next_code=next_code,
        total_count=total_count,
        active_nav="machines",
        result_count=total_count,
        stages=stages,
        lines=ProductionLine.query.filter_by(is_deleted=False, is_active=True).order_by(ProductionLine.code).all(),
        units=Unit.query.filter(Unit.is_active == True, Unit.is_deleted == False).order_by(Unit.code).all(),
    )


def read_capacity():
    # Capacity ke teen number padho: ek ghante me kitna, kis unit me, din me kitne ghante. (values, error) wapas deta hai.
    per_hour = request.form.get('capacity_per_hour', type=float)
    unit_id = request.form.get('capacity_unit_id', type=int)
    hours = request.form.get('hours_per_day', type=float)
    if hours is None:
        hours = 8
    if per_hour is not None and per_hour <= 0:
        return None, "Output per hour must be more than 0."
    if per_hour is not None and not unit_id:
        return None, "Choose the unit of the output (for example KG)."
    if per_hour is not None and db.session.get(Unit, unit_id) is None:
        return None, "Choose a valid unit."
    if not (0 < hours <= 24):
        return None, "Working hours per day must be between 0 and 24."
    return {"per_hour": per_hour, "unit_id": unit_id if per_hour is not None else None, "hours": hours}, None


@machines_bp.route("/machines/add", methods=['POST'])
def machines_add():
    code = generate_next_machine_code()
    name = (request.form.get('name') or "").strip()
    # type=int: value khaali/galat ho to None milta hai — int("") ki tarah crash nahi karta
    work_stage_id = request.form.get('work_stage_id', type=int)
    line_id = request.form.get('line_id', type=int)            # optional: machine kis production line ki hai
    if line_id and not ProductionLine.query.filter_by(id=line_id, is_deleted=False).first():
        line_id = None
    capacity = (request.form.get('capacity') or "").strip() or None
    status = (request.form.get('status') or "active").strip().lower()
    raw_date = (request.form.get('installed_date') or "").strip()
    installed_date = datetime.strptime(raw_date, "%Y-%m-%d").date() if raw_date else None

    if not name or not work_stage_id:
        flash("Machine name and work stage are required.", "error")
        return redirect(url_for('machines.machines_list'))

    work_stage = WorkStage.query.get_or_404(work_stage_id)
    cap, cap_error = read_capacity()
    if cap_error:
        flash(cap_error, "error")
        return redirect(url_for('machines.machines_list'))

    existing = Machines.query.filter_by(code=code).first()
    if existing:
        if existing.is_deleted:
            existing.is_deleted = False
            existing.name = name
            existing.work_stage_id = work_stage_id
            existing.line_id = line_id
            existing.capacity =  capacity
            existing.capacity_per_hour, existing.capacity_unit_id, existing.hours_per_day = cap["per_hour"], cap["unit_id"], cap["hours"]
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
        line_id=line_id,
        capacity=capacity,
        capacity_per_hour=cap["per_hour"],
        capacity_unit_id=cap["unit_id"],
        hours_per_day=cap["hours"],
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

    name = (request.form.get('name') or "").strip()
    # type=int: khaali/galat value pe None — crash nahi
    work_stage_id = request.form.get('work_stage_id', type=int)
    line_id = request.form.get('line_id', type=int)
    if line_id and not ProductionLine.query.filter_by(id=line_id, is_deleted=False).first():
        line_id = None
    capacity = (request.form.get('capacity') or "").strip() or None
    status = (request.form.get('status') or "active").strip().lower()
    raw_date = (request.form.get('installed_date') or "").strip()
    installed_date = datetime.strptime(raw_date, "%Y-%m-%d").date() if raw_date else None

    # Code ab auto-generated — edit pe immutable (form se code nahi aata)
    if not name or not work_stage_id:
        flash("Machine name and work stage are required.", "error")
        return redirect(url_for('machines.machines_list'))

    work_stage = WorkStage.query.get_or_404(work_stage_id)
    cap, cap_error = read_capacity()
    if cap_error:
        flash(cap_error, "error")
        return redirect(url_for('machines.machines_list'))

    m.name = name
    m.work_stage_id = work_stage_id
    m.line_id = line_id
    m.capacity = capacity
    m.capacity_per_hour, m.capacity_unit_id, m.hours_per_day = cap["per_hour"], cap["unit_id"], cap["hours"]
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