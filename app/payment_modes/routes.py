from flask import render_template, Blueprint, url_for, redirect, request, flash
from app.models import PaymentMode
from app.extensions import db

# Payment Modes master (Cash, Bank transfer, UPI, Cheque ...) — Receipt (customer payment) form ke 'Payment mode' dropdown ki source. Hardcoded list nahi, master se.
# Charges / State / Vendor Type master jaisa hi simple pattern.
payment_modes_bp = Blueprint("payment_modes", __name__, template_folder="templates")


def generate_next_payment_mode_code():
    # Auto serial code: last row ka id + 1 => PM-0001, PM-0002 ...
    last_row = PaymentMode.query.order_by(PaymentMode.id.desc()).first()
    if not last_row:
        return "PM-0001"
    next_row = last_row.id + 1
    return f"PM-{next_row:04d}"


@payment_modes_bp.route('/payment_modes')
def payment_modes_list():
    # Soft-deleted rows list me nahi dikhengi (par DB me rehti hain)
    payment_modes = PaymentMode.query.filter(PaymentMode.is_deleted == False).order_by(PaymentMode.code).all()
    total_count = len(payment_modes)
    next_code = generate_next_payment_mode_code()
    return render_template(
        "payment_modes.html",
        payment_modes=payment_modes,
        next_code=next_code,
        total_count=total_count,
        result_count=total_count,
        active_nav='payment_modes',
    )


@payment_modes_bp.route('/payment_modes/add', methods=['POST'])
def payment_modes_add():
    code = generate_next_payment_mode_code()
    name = (request.form.get('name') or "").strip()

    if not code or not name:
        return redirect(url_for('payment_modes.payment_modes_list'))

    existing = PaymentMode.query.filter_by(code=code).first()
    if existing:
        # Agar same code ki row soft-deleted thi to restore kar do
        if existing.is_deleted:
            existing.is_deleted = False
            existing.code = code
            existing.name = name
            existing.is_active = True
            db.session.commit()
            flash("A Payment mode restored with this code.", "success")
            return redirect(url_for('payment_modes.payment_modes_list'))
        flash("A Payment mode with this code already exists.", "error")
        return redirect(url_for('payment_modes.payment_modes_list'))

    mode = PaymentMode(code=code, name=name, is_active=True, is_deleted=False)
    db.session.add(mode)
    db.session.commit()
    flash("Payment mode saved.", "success")
    return redirect(url_for('payment_modes.payment_modes_list'))


@payment_modes_bp.route('/payment_modes/delete/<int:pm_id>', methods=['POST'])
def payment_modes_delete(pm_id):
    # Soft delete — row DB me rehti hai, sirf list se hatti hai
    mode = PaymentMode.query.get_or_404(pm_id)
    mode.is_deleted = True
    db.session.commit()
    flash("Payment mode removed from the list (kept in database).", "success")
    return redirect(url_for('payment_modes.payment_modes_list'))


@payment_modes_bp.route('/payment_modes/toggle/<int:pm_id>', methods=['POST'])
def payment_modes_toggle(pm_id):
    # Active / Stopped flip
    mode = PaymentMode.query.get_or_404(pm_id)
    mode.is_active = not mode.is_active
    db.session.commit()
    return redirect(url_for('payment_modes.payment_modes_list'))


@payment_modes_bp.route('/payment_modes/edit/<int:pm_id>', methods=['POST'])
def payment_modes_edit(pm_id):
    mode = PaymentMode.query.get_or_404(pm_id)
    name = (request.form.get('name') or "").strip()
    if not name:
        return redirect(url_for('payment_modes.payment_modes_list'))
    mode.name = name
    db.session.commit()
    flash("Payment mode Updated.", "success")
    return redirect(url_for('payment_modes.payment_modes_list'))
