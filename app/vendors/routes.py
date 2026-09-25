from flask import render_template, redirect, url_for, Blueprint, request, flash
from app.models import ChartOfAccountsGroup, Ledger, Vendor
from app.extensions import db

vendors_bp = Blueprint("vendors", __name__, template_folder="templates")

@vendors_bp.route("/Vendors")
def vendors_list():
    vendors = Vendor.query.filter(Vendor.is_deleted == False).order_by(Vendor.code).all()
    total_count = len(vendors)

    return render_template(
        "vendors.html",
        vendors=vendors,
        total_count=total_count,
        result_count=total_count,
        active_nav="vendors",
    )

@vendors_bp.route('/vendors/add', methods=['POST'])
def vendors_add():
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
    opening_balance_type = (request.form.get('opening_balance_type') or "Cr").strip()
    bank_name = (request.form.get('bank_name') or "").strip()
    bank_ifsc = (request.form.get('bank_ifsc') or "").strip().upper()
    bank_account = (request.form.get('bank_account') or "").strip()
    vendor_type = (request.form.get('vendor_type') or "").strip()    

    if not code or not name or not state:
        return redirect(url_for('vendors.vendors_list'))

    existing = Vendor.query.filter_by(code=code).first()
    if existing:
        flash("A Vendor with this code already exists.", "error")
        return redirect(url_for('vendors.vendors_list'))    

    # Step 1: "Sundry Creditors" group dhoondo — na mile to pehli baar bana do
    group = ChartOfAccountsGroup.query.filter(ChartOfAccountsGroup.name == "Sundry Creditors").first()
    if not group:
        group = ChartOfAccountsGroup(name="Sundry Creditors", classification="LIABILITY")
        db.session.add(group)
        db.session.flush()

    signed_opening = opening_balance if opening_balance_type == "Cr" else -opening_balance

    # Step 2: is Vendor ka apna Ledger banao (Vendor se PEHLE, kyunki Vendor isko point karega) 
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

    # Step 3: ab Vendor banao — ledger.id already pata hai
    db.session.add(Vendor(
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
        vendor_type=vendor_type,
        bank_name=bank_name,
        bank_ifsc=bank_ifsc,
        bank_account=bank_account,
        ledger_id=ledger.id,
        is_active=True,
        is_deleted=False,

    ))
    db.session.commit()
    flash("Vendor saved — ledger created under Sundry Creditors.", "success")
    return redirect(url_for('vendors.vendors_list'))

@vendors_bp.route("/vendors/toggle/<int:v_id>", methods=['POST'])
def vendors_toggle(v_id):
    v = Vendor.query.get_or_404(v_id)

    v.is_active =  not v.is_active
    db.session.commit()
    return redirect(url_for('vendors.vendors_list'))    

@vendors_bp.route('/vendors/edit/<int:v_id>', methods=['POST']) 
def vendors_edit(v_id):
    v = Vendor.query.get_or_404(v_id)

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
    opening_balance_type = (request.form.get('opening_balance_type') or "Cr").strip()
    bank_name = (request.form.get('bank_name') or "").strip()
    bank_ifsc = (request.form.get('bank_ifsc') or "").strip().upper()
    bank_account = (request.form.get('bank_account') or "").strip()
    vendor_type = (request.form.get('vendor_type') or "").strip()

    if not code or not name or not state:
        return redirect(url_for('vendors.vendors_list'))

    dup = Vendor.query.filter(Vendor.code == code, Vendor.id != v.id).first()
    if dup:
        flash("A Vendor with this code already exists.", "error")
        return redirect(url_for('vendors.vendors_list'))

    ledger = v.ledger

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

    v.code = code
    v.name = name
    v.contact_person=contact_person
    v.mobile=mobile
    v.email=email
    v.address=address
    v.state=state
    v.gstin=gstin or None
    v.pan=pan or None
    v.payment_terms=payment_terms
    v.vendor_type=vendor_type
    v.bank_name=bank_name
    v.bank_ifsc=bank_ifsc
    v.bank_account=bank_account
    v.is_deleted = False
    db.session.commit()
    flash("Vendor Updated — ledger Updated under Sundry Creditors.", "success")
    return redirect(url_for('vendors.vendors_list'))





       