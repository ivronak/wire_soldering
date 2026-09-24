from flask import render_template, Blueprint, redirect, url_for, request, flash
from app.models import TaxRate
from app.extensions import db

tax_rates_bp = Blueprint("tax_rates", __name__, template_folder='templates')

@tax_rates_bp.route('/tax_rates')
def tax_rates_list():
    tax_rates = TaxRate.query.filter(TaxRate.is_deleted == False).all()
    total_count = len(tax_rates)

    return render_template(
        "tax_rates.html",
        tax_rates=tax_rates,
        total_count=total_count,
        result_count=total_count,
    )

@tax_rates_bp.route('/tax_rates/add', methods=['POST'])
def tax_rates_add():

    code = (request.form.get('code') or "").strip().upper()
    rate_percent = float(request.form.get('rate_percent')) if (request.form.get('rate_percent') or "").strip() else None
    label = (request.form.get('label') or "").strip()

    if not code or not label or rate_percent is None:
        return redirect(url_for('tax_rates.tax_rates_list'))

    existing = TaxRate.query.filter_by(code=code).first()
    if existing:
        if existing.is_deleted:

            existing.is_deleted = False
            existing.code = code
            existing.rate_percent = rate_percent
            existing.label = label
            existing.is_active = True
            db.commit.session()
            flash("A Tax Rate restored with this code.", "success")
            return redirect(url_for('tax_rates.tax_rates_list'))

        flash("A Tax Rate with this code already exists.", "error")
        return redirect(url_for('tax_rates.tax_rates_list'))

    db.session.add(TaxRate(
        code=code,
        rate_percent=rate_percent,
        label=label,
        is_active=True,
        is_deleted=False,

    ))    
    db.session.commit()
    flash("Tax Rate saved.", "success")
    return redirect(url_for('tax_rates.tax_rates_list'))

@tax_rates_bp.route('/tax_rates/toggle/<int:r_id>', methods=['POST'])
def tax_rates_toggle(r_id):
    r = TaxRate.query.get_or_404(r_id)

    r.is_active = not r.is_active
    db.session.commit()

    return redirect(url_for('tax_rates.tax_rates_list'))

@tax_rates_bp.route('/tax_rates/edit/<int:r_id>', methods=['POST'])
def tax_rates_edit(r_id):
    r = TaxRate.query.get_or_404(r_id)

    code = (request.form.get('code') or "").strip().upper()
    rate_percent = float(request.form.get('rate_percent')) if (request.form.get('rate_percent') or "").strip() else None
    label = (request.form.get('label') or "").strip()

    if not code or not label or rate_percent is None:
        return redirect(url_for('tax_rates.tax_rates_list'))

    dup = TaxRate.query.filter(TaxRate.code == code, TaxRate.id != r_id).first()
    if dup:
        flash("A Tax Rate with this code already exists.", "error")
        return redirect(url_for('tax_rates.tax_rates_list'))


    r.code = code
    r.rate_percent = rate_percent
    r.label = label
    r.is_deleted = False
    db.session.commit()
    flash("Tax Rate updated.", "success")
    return redirect(url_for('tax_rates.tax_rates_list'))

@tax_rates_bp.route('/tax_rates/delete/<int:r_id>', methods=['POST'])
def tax_rates_delete(r_id):
    r = TaxRate.query.get_or_404(r_id)

    r.is_deleted = True
    db.session.commit()
    flash("Tax Rate removed from the list (kept in database).", "success")
    return redirect(url_for('tax_rates.tax_rates_list'))