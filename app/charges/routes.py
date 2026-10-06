from flask import render_template, Blueprint, url_for, redirect, request, flash
from app.models import Charge
from app.extensions import db

charges_bp = Blueprint("charges", __name__, template_folder="templates")

def generate_next_charge_code():

    last_charge = Charge.query.order_by(Charge.id.desc()).first()
    if not last_charge:
        return "CHG-0001"

    next_charge = last_charge.id +1 
    return f"CHG-{next_charge:04d}"


@charges_bp.route('/charges')
def charges_list():
    charges = Charge.query.filter(Charge.is_deleted == False).order_by(Charge.code).all()
    total_count=len(charges)
    next_code = generate_next_charge_code()

    return render_template(
        "charges.html",
        charges=charges,
        next_code=next_code,
        total_count=total_count,
        result_count=total_count,
        active_nav='charges',
    )

@charges_bp.route('/charges/add', methods=['POST'])
def charges_add():

    code = generate_next_charge_code()
    name = (request.form.get('name') or "").strip()


    if not code or not name:
        return redirect(url_for('charges.charges_list'))

    existing = Charge.query.filter_by(code=code).first()
    if existing:
        if existing.is_deleted:

            existing.is_deleted = False
            existing.code = code
            existing.name = name
            existing.is_active = True
            db.session.commit()
            flash("A Charge restored with this code.", "success")
            return redirect(url_for('charges.charges_list'))

        flash("A Charge with this code already exists.", "error")
        return redirect(url_for('charges.charges_list'))

    db.session.add(Charge(
        code=code,
        name=name,
        is_active=True,
        is_deleted=False,

    ))    
    db.session.commit()
    flash("Charge saved.", "success")
    return redirect(url_for('charges.charges_list'))


@charges_bp.route('/charges/delete/<int:c_id>', methods=['POST'])
def charges_delete(c_id):
    c = Charge.query.get_or_404(c_id)

    c.is_deleted = True
    db.session.commit()
    flash("Charge removed from the list (kept in database).", "success")
    return redirect(url_for('charges.charges_list'))

@charges_bp.route('/charges/toggle/<int:c_id>', methods=['POST'])
def charges_toggle(c_id):
    c = Charge.query.get_or_404(c_id)

    c.is_active = not c.is_active
    db.session.commit()
    return redirect(url_for('charges.charges_list'))

@charges_bp.route('/charges/edit/<int:c_id>', methods=['POST'])
def charges_edit(c_id):
    c = Charge.query.get_or_404(c_id)
    # .get() ke bina, name field missing ho to None.strip() crash karta tha
    name = (request.form.get('name') or "").strip()

    if not name:
       return redirect(url_for('charges.charges_list'))

    c.name = name
    db.session.commit()
    flash("Charge Updated.", "success")
    return redirect(url_for('charges.charges_list'))