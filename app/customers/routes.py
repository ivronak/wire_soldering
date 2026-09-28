from flask import render_template, Blueprint, redirect, url_for, request, flash
from app.models import Customer, Ledger, ChartOfAccountsGroup
from app.extensions import db
from app.constants import INDIAN_STATES

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
        states=INDIAN_STATES,
    )

@customers_bp.route('/customers/add', methods=['POST'])
def customers_add():
    code = (request.form.get('code') or "").strip().upper()
    name = (request.form.get('name') or "").strip()
    contact_person = (request.form.get('contact_person') or "").strip()
    mobile = (request.form.get('mobile') or "").strip()
    email = (request.form.get('email') or "").strip()
    address = (request.form.get('address') or "").strip()
    state = (request.form.get('state') or "").strip()
    gstin = (request.form.get('gstin') or "").strip().upper()
    pan = (request.form.get('pan') or "").strip().upper()
    payment_terms = (request.form.get('payment_terms') or "").strip()
    opening_balance = float(request.form.get('opening_balance')) if (request.form.get('opening_balance') or "").strip() else 0
    opening_balance_type = (request.form.get('opening_balance_type') or "Dr").strip()
    bank_name = (request.form.get('bank_name') or "").strip()
    bank_ifsc = (request.form.get('bank_ifsc') or "").strip().upper()
    bank_account = (request.form.get('bank_account') or "").strip()
    credit_limit = float(request.form.get('credit_limit')) if (request.form.get('credit_limit') or "").strip() else None

    if not code or not name or not state:
        return redirect(url_for('customers.customers_list'))

    existing = Customer.query.filter(Customer.code == code).first()
    if existing:
        flash("A Customer with this code already exists.", "error")
        return redirect(url_for('customers.customers_list'))    

    # Step 1: "Sundry Debtors" group dhoondo — na mile to pehli baar bana do
    group = ChartOfAccountsGroup.query.filter(ChartOfAccountsGroup.name == "Sundry Debtors").first()
    if not group:
        group = ChartOfAccountsGroup(name="Sundry Debtors", classification="ASSET")
        db.session.add(group)
        db.session.flush()    

    signed_opening = opening_balance if opening_balance_type == "Cr" else -opening_balance

    # Step 2: is Customer ka apna Ledger banao (Customer se PEHLE, kyunki Customer isko point karega) 
    ledger = Ledger(
        name=name,
        group_id=group.id,
        opening_balance=opening_balance,
        opening_balance_type=opening_balance_type,
        current_balance=signed_opening,
        gstin=gstin or None,
    )
    db.session.add(ledger)
    db.session.flush()

    # Step 3: ab Customer banao — ledger.id already pata hai
    db.session.add(Customer(
        code=code,
        name=name,
        contact_person=contact_person,
        mobile=mobile,
        email=email,
        address=address,
        state=state,
        gstin=gstin or None,
        pan=pan or None,
        payment_terms=payment_terms,
        credit_limit=credit_limit,
        bank_name=bank_name,
        bank_ifsc=bank_ifsc,
        bank_account=bank_account,
        ledger_id=ledger.id,
        is_active=True,
        is_deleted=False,

    ))
    db.session.commit()
    flash("Customer saved — ledger created under Sundry Debtors.", "success")
    return redirect(url_for('customers.customers_list'))

@customers_bp.route("/customers/toggle/<int:c_id>", methods=['POST'])
def customers_toggle(c_id):
    c = Customer.query.get_or_404(c_id)

    c.is_active =  not c.is_active
    db.session.commit()
    return redirect(url_for('customers.customers_list'))

@customers_bp.route('/customers/edit/<int:c_id>', methods=['POST'])
def customers_edit(c_id):
    c = Customer.query.get_or_404(c_id)

    code = (request.form.get('code') or "").strip().upper()
    name = (request.form.get('name') or "").strip()
    contact_person = (request.form.get('contact_person') or "").strip()
    mobile = (request.form.get('mobile') or "").strip()
    email = (request.form.get('email') or "").strip()
    address = (request.form.get('address') or "").strip()
    state = (request.form.get('state') or "").strip()
    gstin = (request.form.get('gstin') or "").strip().upper()
    pan = (request.form.get('pan') or "").strip().upper()
    payment_terms = (request.form.get('payment_terms') or "").strip()
    opening_balance = float(request.form.get('opening_balance')) if (request.form.get('opening_balance') or "").strip() else 0
    opening_balance_type = (request.form.get('opening_balance_type') or "Dr").strip()
    bank_name = (request.form.get('bank_name') or "").strip()
    bank_ifsc = (request.form.get('bank_ifsc') or "").strip().upper()
    bank_account = (request.form.get('bank_account') or "").strip()
    credit_limit = float(request.form.get('credit_limit')) if (request.form.get('credit_limit') or "").strip() else None

    if not code or not name or not state:
        return redirect(url_for('customers.customers_list'))

    dup = Customer.query.filter(Customer.code == code, Customer.id != c.id).first()
    if dup:
        flash("A Customer with this code already exists.", "error")
        return redirect(url_for('customers.customers_list'))
        
    ledger = c.ledger

    def signed_ammount(bal, bal_type):
        return bal if bal_type == "Cr" else -bal

    old_op_bal = signed_ammount(ledger.opening_balance, ledger.opening_balance_type)   
    new_op_bal = signed_ammount(opening_balance, opening_balance_type) 
        
    ledger.name = name
    ledger.opening_balance = opening_balance
    ledger.opening_balance_type = opening_balance_type
    ledger.current_balance = ledger.current_balance + (new_op_bal-old_op_bal)
    ledger.gstin = gstin or None
    db.session.flush()

    c.code = code
    c.name = name
    c.contact_person=contact_person
    c.mobile=mobile
    c.email=email
    c.address=address
    c.state=state
    c.gstin=gstin or None
    c.pan=pan or None
    c.payment_terms=payment_terms
    c.credit_limit=credit_limit
    c.bank_name=bank_name
    c.bank_ifsc=bank_ifsc
    c.bank_account=bank_account
    c.is_deleted = False
    db.session.commit()
    flash("Customer Updated — ledger Updated under Sundry Debtors.", "success")
    return redirect(url_for('customers.customers_list'))    