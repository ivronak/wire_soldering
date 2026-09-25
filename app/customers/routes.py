from flask import render_template, Blueprint, redirect, url_for, request, flash
from app.models import Customer, Ledger, ChartOfAccountsGroup
from app.extensions import db

customers_bp = Blueprint("customers", __name__, template_folder='templates')

@customers_bp.route('/customers')
def customers_list():
    customers = Customer.query.filter(Customer.is_deleted == False).order_by(Customer.code).all()
    total_count = len(customers)

    return render_template(
        "customers.html",
        customers=customers,
        active_nav="customers",
        total_count=total_count,
        result_count=total_count,
    )

# @customers_bp.route('/customers/add', methods=['POST'])
# def customers_add():
    # code = (request.form.get('code') or "").strip().upper()
    # name = (request.form.get('name') or "").strip()
    # contact_person = (request.form.get('contact_person') or "").strip()
    # mobile = (request.form.get('mobile') or "").strip()
    # email = (request.form.get('email') or "").strip()
    # address = (request.form.get('address') or "").strip()
    # state = (request.form.get('state') or "").strip()
    # gstin = (request.form.get('gstin') or "").strip().upper()
    # pan = (request.form.get('pan') or "").strip().upper()
    # payment_terms = (request.form.get('payment_terms') or "").strip()
    # opening_balance = float(request.form.get('opening_balance')) if (request.form.get('opening_balance') or "").strip() else 0
    # opening_balance_type = (request.form.get('opening_balance_type') or "Cr").strip()
    # bank_name = (request.form.get('bank_name') or "").strip()
    # bank_ifsc = (request.form.get('bank_ifsc') or "").strip().upper()
    # bank_account = (request.form.get('bank_account') or "").strip()
    # vendor_type = (request.form.get('vendor_type') or "").strip()    
