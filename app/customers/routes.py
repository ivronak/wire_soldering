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
