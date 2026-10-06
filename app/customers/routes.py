from flask import render_template, Blueprint, redirect, url_for, request, flash
from app.models import Customer, Ledger, ChartOfAccountsGroup, State, PaymentTerm
from app.extensions import db

customers_bp = Blueprint("customers", __name__, template_folder='templates')


def generate_next_customer_code():
    # Auto-serial (C-0001, C-0002 ...) — form se code nahi aata
    last_row = Customer.query.order_by(Customer.id.desc()).first()
    if not last_row:
        return "C-0001"
    next_row = last_row.id + 1
    return f"C-{next_row:04d}"


@customers_bp.route('/customers')
def customers_list():
    customers = Customer.query.filter(Customer.is_deleted == False).order_by(Customer.code).all()
    total_count = len(customers)
    next_code = generate_next_customer_code()

    return render_template(
        "customers.html",
        customers=customers,
        active_nav="customers",
        next_code=next_code,
        total_count=total_count,
        result_count=total_count,
        states=State.query.filter(State.is_deleted == False, State.is_active == True).order_by(State.name).all(),
        # Payment terms dropdown ab Payment Terms Master se — sirf live (deleted nahi, active)
        payment_terms=PaymentTerm.query.filter(PaymentTerm.is_deleted == False, PaymentTerm.is_active == True).order_by(PaymentTerm.name).all(),
    )

@customers_bp.route('/customers/add', methods=['POST'])
def customers_add():
    # Code auto-generate hota hai — form se nahi aata
    code = generate_next_customer_code()
    name = (request.form.get('name') or "").strip()
    contact_person = (request.form.get('contact_person') or "").strip()
    mobile = (request.form.get('mobile') or "").strip()
    email = (request.form.get('email') or "").strip()
    address = (request.form.get('address') or "").strip()
    state_id = request.form.get('state_id', type=int)
    gstin = (request.form.get('gstin') or "").strip().upper()
    pan = (request.form.get('pan') or "").strip().upper()
    # Payment terms ab master se aata hai (OPTIONAL) — form se id
    payment_terms_id = request.form.get('payment_terms_id', type=int)
    opening_balance = float(request.form.get('opening_balance')) if (request.form.get('opening_balance') or "").strip() else 0
    opening_balance_type = (request.form.get('opening_balance_type') or "Dr").strip()
    bank_name = (request.form.get('bank_name') or "").strip()
    bank_ifsc = (request.form.get('bank_ifsc') or "").strip().upper()
    bank_account = (request.form.get('bank_account') or "").strip()
    credit_limit = float(request.form.get('credit_limit')) if (request.form.get('credit_limit') or "").strip() else None

    if not name or not state_id:
        return redirect(url_for('customers.customers_list'))

    # Dropdown se aaya state_id sach me valid State hona chahiye
    if not State.query.filter(State.id == state_id, State.is_deleted == False).first():
        flash("Please select a valid state.", "error")
        return redirect(url_for('customers.customers_list'))

    # Payment terms optional hai — par agar diya hai to valid (deleted nahi) hona chahiye
    if payment_terms_id and not PaymentTerm.query.filter(PaymentTerm.id == payment_terms_id, PaymentTerm.is_deleted == False).first():
        flash("Please select valid payment terms.", "error")
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
        state_id=state_id,
        gstin=gstin or None,
        pan=pan or None,
        payment_terms_id=payment_terms_id,
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

    name = (request.form.get('name') or "").strip()
    contact_person = (request.form.get('contact_person') or "").strip()
    mobile = (request.form.get('mobile') or "").strip()
    email = (request.form.get('email') or "").strip()
    address = (request.form.get('address') or "").strip()
    state_id = request.form.get('state_id', type=int)
    gstin = (request.form.get('gstin') or "").strip().upper()
    pan = (request.form.get('pan') or "").strip().upper()
    # Payment terms ab master se aata hai (OPTIONAL) — form se id
    payment_terms_id = request.form.get('payment_terms_id', type=int)
    opening_balance = float(request.form.get('opening_balance')) if (request.form.get('opening_balance') or "").strip() else 0
    opening_balance_type = (request.form.get('opening_balance_type') or "Dr").strip()
    bank_name = (request.form.get('bank_name') or "").strip()
    bank_ifsc = (request.form.get('bank_ifsc') or "").strip().upper()
    bank_account = (request.form.get('bank_account') or "").strip()
    credit_limit = float(request.form.get('credit_limit')) if (request.form.get('credit_limit') or "").strip() else None

    if not name or not state_id:
        return redirect(url_for('customers.customers_list'))

    # Dropdown se aaya state_id sach me valid State hona chahiye
    if not State.query.filter(State.id == state_id, State.is_deleted == False).first():
        flash("Please select a valid state.", "error")
        return redirect(url_for('customers.customers_list'))

    # Payment terms optional hai — par agar diya hai to valid (deleted nahi) hona chahiye
    if payment_terms_id and not PaymentTerm.query.filter(PaymentTerm.id == payment_terms_id, PaymentTerm.is_deleted == False).first():
        flash("Please select valid payment terms.", "error")
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

    c.name = name
    c.contact_person=contact_person
    c.mobile=mobile
    c.email=email
    c.address=address
    c.state_id=state_id
    c.gstin=gstin or None
    c.pan=pan or None
    c.payment_terms_id=payment_terms_id
    c.credit_limit=credit_limit
    c.bank_name=bank_name
    c.bank_ifsc=bank_ifsc
    c.bank_account=bank_account
    c.is_deleted = False
    db.session.commit()
    flash("Customer Updated — ledger Updated under Sundry Debtors.", "success")
    return redirect(url_for('customers.customers_list'))    
