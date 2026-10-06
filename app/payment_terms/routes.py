from flask import render_template, Blueprint, url_for, redirect, request, flash
from app.models import PaymentTerm
from app.extensions import db

# Payment Terms master — Vendor / Customer / Purchase order dropdowns ki source.
# Charges / State / Vendor Type master jaisa hi simple pattern.
payment_terms_bp = Blueprint("payment_terms", __name__, template_folder="templates")


def generate_next_payment_term_code():
    # Auto serial code: last row ka id + 1 => PT-0001, PT-0002 ...
    last_row = PaymentTerm.query.order_by(PaymentTerm.id.desc()).first()
    if not last_row:
        return "PT-0001"
    next_row = last_row.id + 1
    return f"PT-{next_row:04d}"


@payment_terms_bp.route('/payment_terms')
def payment_terms_list():
    # Soft-deleted rows list me nahi dikhengi (par DB me rehti hain)
    payment_terms = PaymentTerm.query.filter(PaymentTerm.is_deleted == False).order_by(PaymentTerm.code).all()
    total_count = len(payment_terms)
    next_code = generate_next_payment_term_code()
    return render_template(
        "payment_terms.html",
        payment_terms=payment_terms,
        next_code=next_code,
        total_count=total_count,
        result_count=total_count,
        active_nav='payment_terms',
    )


@payment_terms_bp.route('/payment_terms/add', methods=['POST'])
def payment_terms_add():
    code = generate_next_payment_term_code()
    name = (request.form.get('name') or "").strip()

    if not code or not name:
        return redirect(url_for('payment_terms.payment_terms_list'))

    existing = PaymentTerm.query.filter_by(code=code).first()
    if existing:
        # Agar same code ki row soft-deleted thi to restore kar do
        if existing.is_deleted:
            existing.is_deleted = False
            existing.code = code
            existing.name = name
            existing.is_active = True
            db.session.commit()
            flash("A Payment term restored with this code.", "success")
            return redirect(url_for('payment_terms.payment_terms_list'))
        flash("A Payment term with this code already exists.", "error")
        return redirect(url_for('payment_terms.payment_terms_list'))

    term = PaymentTerm(code=code, name=name, is_active=True, is_deleted=False)
    db.session.add(term)
    db.session.commit()
    flash("Payment term saved.", "success")
    return redirect(url_for('payment_terms.payment_terms_list'))


@payment_terms_bp.route('/payment_terms/delete/<int:pt_id>', methods=['POST'])
def payment_terms_delete(pt_id):
    # Soft delete — row DB me rehti hai, sirf list se hatti hai
    term = PaymentTerm.query.get_or_404(pt_id)
    term.is_deleted = True
    db.session.commit()
    flash("Payment term removed from the list (kept in database).", "success")
    return redirect(url_for('payment_terms.payment_terms_list'))


@payment_terms_bp.route('/payment_terms/toggle/<int:pt_id>', methods=['POST'])
def payment_terms_toggle(pt_id):
    # Active / Stopped flip
    term = PaymentTerm.query.get_or_404(pt_id)
    term.is_active = not term.is_active
    db.session.commit()
    return redirect(url_for('payment_terms.payment_terms_list'))


@payment_terms_bp.route('/payment_terms/edit/<int:pt_id>', methods=['POST'])
def payment_terms_edit(pt_id):
    term = PaymentTerm.query.get_or_404(pt_id)
    name = (request.form.get('name') or "").strip()
    if not name:
        return redirect(url_for('payment_terms.payment_terms_list'))
    term.name = name
    db.session.commit()
    flash("Payment term Updated.", "success")
    return redirect(url_for('payment_terms.payment_terms_list'))
