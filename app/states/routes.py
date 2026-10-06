from flask import render_template, Blueprint, url_for, redirect, request, flash
from app.models import State
from app.extensions import db

states_bp = Blueprint("states", __name__, template_folder="templates")

def generate_next_state_code():
    # Charges jaisa serial: last row ka id + 1, warna pehla ST-0001
    last_state = State.query.order_by(State.id.desc()).first()
    if not last_state:
        return "ST-0001"

    next_state = last_state.id + 1
    return f"ST-{next_state:04d}"


@states_bp.route('/states')
def states_list():
    states = State.query.filter(State.is_deleted == False).order_by(State.code).all()
    total_count = len(states)
    next_code = generate_next_state_code()

    return render_template(
        "states.html",
        states=states,
        next_code=next_code,
        total_count=total_count,
        result_count=total_count,
        active_nav='states',
    )


@states_bp.route('/states/add', methods=['POST'])
def states_add():
    # Code form se nahi lete - route khud generate karta hai (form ka field disabled hai)
    code = generate_next_state_code()
    name = (request.form.get('name') or "").strip()
    gst_state_code = (request.form.get('gst_state_code') or "").strip()

    if not code or not name or not gst_state_code:
        flash("State name and GST state code are required.", "error")
        return redirect(url_for('states.states_list'))

    if len(gst_state_code) != 2 or not gst_state_code.isdigit():
        flash("GST state code must be 2 digits (example: 24 for Gujarat).", "error")
        return redirect(url_for('states.states_list'))

    existing = State.query.filter_by(code=code).first()
    if existing:
        if existing.is_deleted:
            # Soft-deleted row same code pe wapas - restore karo, naya row nahi
            existing.is_deleted = False
            existing.code = code
            existing.name = name
            existing.gst_state_code = gst_state_code
            existing.is_active = True
            db.session.commit()
            flash("A State restored with this code.", "success")
            return redirect(url_for('states.states_list'))

        flash("A State with this code already exists.", "error")
        return redirect(url_for('states.states_list'))

    # GST state code unique hona chahiye - do state ka same GST code galat hai
    duplicate_gst = State.query.filter(
        State.gst_state_code == gst_state_code,
        State.is_deleted == False
    ).first()
    if duplicate_gst:
        flash(f"GST state code {gst_state_code} is already used by {duplicate_gst.name}.", "error")
        return redirect(url_for('states.states_list'))

    db.session.add(State(
        code=code,
        name=name,
        gst_state_code=gst_state_code,
        is_active=True,
        is_deleted=False,
    ))
    db.session.commit()
    flash("State saved.", "success")
    return redirect(url_for('states.states_list'))


@states_bp.route('/states/edit/<int:s_id>', methods=['POST'])
def states_edit(s_id):
    s = State.query.get_or_404(s_id)

    name = (request.form.get('name') or "").strip()
    gst_state_code = (request.form.get('gst_state_code') or "").strip()

    if not name or not gst_state_code:
        flash("State name and GST state code are required.", "error")
        return redirect(url_for('states.states_list'))

    if len(gst_state_code) != 2 or not gst_state_code.isdigit():
        flash("GST state code must be 2 digits (example: 24 for Gujarat).", "error")
        return redirect(url_for('states.states_list'))

    duplicate_gst = State.query.filter(
        State.gst_state_code == gst_state_code,
        State.id != s_id,
        State.is_deleted == False
    ).first()
    if duplicate_gst:
        flash(f"GST state code {gst_state_code} is already used by {duplicate_gst.name}.", "error")
        return redirect(url_for('states.states_list'))

    # code kabhi nahi badalta - sirf name aur GST state code
    s.name = name
    s.gst_state_code = gst_state_code

    db.session.commit()
    flash("State updated.", "success")
    return redirect(url_for('states.states_list'))


@states_bp.route('/states/toggle/<int:s_id>', methods=['POST'])
def states_toggle(s_id):
    s = State.query.get_or_404(s_id)

    s.is_active = not s.is_active
    db.session.commit()

    return redirect(url_for('states.states_list'))


@states_bp.route('/states/delete/<int:s_id>', methods=['POST'])
def states_delete(s_id):
    s = State.query.get_or_404(s_id)

    # Soft delete - row DB me rahegi, list se hat jaayegi
    s.is_deleted = True
    db.session.commit()
    flash("State removed from the list (kept in database).", "success")
    return redirect(url_for('states.states_list'))
