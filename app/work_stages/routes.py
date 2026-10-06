from flask import render_template, redirect, url_for, Blueprint, request, flash
from app.models import WorkStage
from app.extensions import db

work_stages_bp = Blueprint("work_stages", __name__, template_folder="templates")

def generate_next_work_stage_code():
    # Auto-serial (WS-0001, WS-0002 ...) — form se code nahi aata
    last_row = WorkStage.query.order_by(WorkStage.id.desc()).first()
    if not last_row:
        return "WS-0001"
    next_row = last_row.id + 1
    return f"WS-{next_row:04d}"

@work_stages_bp.route("/work_stages")
def work_stages_list():
    # Pehle khaali table pe "Cutting" stage apne aap ban jaati thi — hata diya:
    # master data user UI se daale, code me hardcode nahi (CLAUDE.md §5 rule 1)
    stages = WorkStage.query.filter(WorkStage.is_deleted == False).all()
    total_count = len(stages)
    next_code = generate_next_work_stage_code()

    return render_template(
        "work_stages.html",
        active_nav="work_stages",
        stages=stages,
        next_code=next_code,
        total_count=total_count,
        result_count=total_count,
    )

@work_stages_bp.route('/work_stages/add', methods=['POST'])
def work_stages_add():
    # Code ab auto-generated hai — form se nahi aata
    code = generate_next_work_stage_code()
    name = (request.form.get('name') or "").strip()
    sort_order = request.form.get('sort_order') or 0

    if not name:
        return redirect(url_for('work_stages.work_stages_list'))

    existing = WorkStage.query.filter_by(code=code).first()
    if existing :
        if existing.is_deleted:
            existing.is_deleted = False
            existing.code = code
            existing.name = name
            existing.sort_order = sort_order
            existing.is_active = True
            db.session.commit()
            flash("Work Stage restored with this code.","success")
            return redirect(url_for('work_stages.work_stages_list'))

        flash("A Work Stage with this code already exists.","error")
        return redirect(url_for('work_stages.work_stages_list'))

    db.session.add(WorkStage(
        code=code,
        name=name,
        sort_order=sort_order,
        is_active=True,
        is_deleted=False,
    ))
    db.session.commit()
    flash("Work Stage saved.", "success")
    return redirect(url_for('work_stages.work_stages_list'))

@work_stages_bp.route('/work_stages/edit/<int:stage_id>', methods=['POST'])
def work_stages_edit(stage_id):
    s = WorkStage.query.get_or_404(stage_id)

    name = (request.form.get('name') or "").strip()
    sort_order = request.form.get('sort_order') or 0

    if not name:
        return redirect(url_for('work_stages.work_stages_list'))

    # Code ab auto-generated — edit pe immutable
    s.name = name
    s.sort_order = sort_order
    db.session.commit()
    flash("Work Stage Updated", "success")
    return redirect(url_for('work_stages.work_stages_list'))

@work_stages_bp.route('/work_stages/delete/<int:stage_id>', methods=['POST'])
def work_stages_delete(stage_id):
    s = WorkStage.query.get_or_404(stage_id)
    s.is_deleted = True
    db.session.commit()

    flash("Work Stage removed from the list (kept in database).", "success")
    return redirect(url_for('work_stages.work_stages_list'))

@work_stages_bp.route('/work_stages/toggle/<int:stage_id>', methods=['POST'])
def work_stages_toggle(stage_id):
    s = WorkStage.query.get_or_404(stage_id)
    s.is_active = not s.is_active
    db.session.commit()

    return redirect(url_for('work_stages.work_stages_list'))
