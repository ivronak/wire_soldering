from flask import render_template, redirect, url_for, Blueprint, request, flash
from app.models import ChartOfAccountsGroup, Ledger, Vendor, State, VendorType, PaymentTerm
from app.extensions import db

vendors_bp = Blueprint("vendors", __name__, template_folder="templates")


def generate_next_vendor_code():
    # Auto-serial (V-0001, V-0002 ...) — form se code nahi aata
    last_row = Vendor.query.order_by(Vendor.id.desc()).first()
    if not last_row:
        return "V-0001"
    next_row = last_row.id + 1
    return f"V-{next_row:04d}"


def read_lead_time():
    # Lead time (din) optional: khaali = None. Diya ho to 0 se 365 ke beech poora number. (value, None) ya (None, "error")
    raw = (request.form.get('lead_time_days') or "").strip()
    if not raw:
        return None, None
    if not raw.isdigit() or int(raw) > 365:
        return None, "Lead time must be a whole number of days between 0 and 365."
    return int(raw), None



@vendors_bp.route("/vendors")
def vendors_list():
    vendors = Vendor.query.filter(Vendor.is_deleted == False).order_by(Vendor.code).all()
    total_count = len(vendors)
    next_code = generate_next_vendor_code()

    return render_template(
        "vendors.html",
        vendors=vendors,
        total_count=total_count,
        result_count=total_count,
        active_nav="vendors",
        next_code=next_code,
        # Dropdown ab State Master se — sirf live (deleted nahi, active) states
        states=State.query.filter(State.is_deleted == False, State.is_active == True).order_by(State.name).all(),
        # Vendor Type dropdown ab Vendor Type Master se — sirf live (deleted nahi, active) types
        vendor_types=VendorType.query.filter(VendorType.is_deleted == False, VendorType.is_active == True).order_by(VendorType.name).all(),
        # Payment terms dropdown ab Payment Terms Master se — sirf live (deleted nahi, active)
        payment_terms=PaymentTerm.query.filter(PaymentTerm.is_deleted == False, PaymentTerm.is_active == True).order_by(PaymentTerm.name).all(),
    )

@vendors_bp.route('/vendors/add', methods=['POST'])
def vendors_add():
    # Code ab auto-generated — form se code nahi aata
    code = generate_next_vendor_code()
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
    opening_balance_type = (request.form.get('opening_balance_type') or "Cr").strip()
    bank_name = (request.form.get('bank_name') or "").strip()
    bank_ifsc = (request.form.get('bank_ifsc') or "").strip().upper()
    bank_account = (request.form.get('bank_account') or "").strip()
    # Vendor type ab master se aata hai (OPTIONAL) — form se id
    vendor_type_id = request.form.get('vendor_type_id', type=int)

    if not name or not state_id:
        return redirect(url_for('vendors.vendors_list'))

    # Dropdown se aaya state_id sach me valid State hona chahiye
    if not State.query.filter(State.id == state_id, State.is_deleted == False).first():
        flash("Please select a valid state.", "error")
        return redirect(url_for('vendors.vendors_list'))

    # Vendor type optional hai — par agar diya hai to valid (deleted nahi) hona chahiye
    if vendor_type_id and not VendorType.query.filter(VendorType.id == vendor_type_id, VendorType.is_deleted == False).first():
        flash("Please select a valid vendor type.", "error")
        return redirect(url_for('vendors.vendors_list'))

    # Payment terms optional hai — par agar diya hai to valid (deleted nahi) hona chahiye
    if payment_terms_id and not PaymentTerm.query.filter(PaymentTerm.id == payment_terms_id, PaymentTerm.is_deleted == False).first():
        flash("Please select valid payment terms.", "error")
        return redirect(url_for('vendors.vendors_list'))

    lead_time_days, lead_error = read_lead_time()
    if lead_error:
        flash(lead_error, "error")
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
        state_id=state_id,
        gstin=gstin or None,
        pan=pan or None,
        payment_terms_id=payment_terms_id,
        lead_time_days=lead_time_days,
        vendor_type_id=vendor_type_id,
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

    # Code ab auto-generated — edit pe immutable (form se code nahi aata)
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
    opening_balance_type = (request.form.get('opening_balance_type') or "Cr").strip()
    bank_name = (request.form.get('bank_name') or "").strip()
    bank_ifsc = (request.form.get('bank_ifsc') or "").strip().upper()
    bank_account = (request.form.get('bank_account') or "").strip()
    # Vendor type ab master se aata hai (OPTIONAL) — form se id
    vendor_type_id = request.form.get('vendor_type_id', type=int)

    if not name or not state_id:
        return redirect(url_for('vendors.vendors_list'))

    if not State.query.filter(State.id == state_id, State.is_deleted == False).first():
        flash("Please select a valid state.", "error")
        return redirect(url_for('vendors.vendors_list'))

    # Vendor type optional hai — par agar diya hai to valid (deleted nahi) hona chahiye
    if vendor_type_id and not VendorType.query.filter(VendorType.id == vendor_type_id, VendorType.is_deleted == False).first():
        flash("Please select a valid vendor type.", "error")
        return redirect(url_for('vendors.vendors_list'))

    # Payment terms optional hai — par agar diya hai to valid (deleted nahi) hona chahiye
    if payment_terms_id and not PaymentTerm.query.filter(PaymentTerm.id == payment_terms_id, PaymentTerm.is_deleted == False).first():
        flash("Please select valid payment terms.", "error")
        return redirect(url_for('vendors.vendors_list'))

    lead_time_days, lead_error = read_lead_time()
    if lead_error:
        flash(lead_error, "error")
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

    v.name = name
    v.contact_person=contact_person
    v.mobile=mobile
    v.email=email
    v.address=address
    v.state_id=state_id
    v.gstin=gstin or None
    v.pan=pan or None
    v.payment_terms_id=payment_terms_id
    v.lead_time_days=lead_time_days
    v.vendor_type_id=vendor_type_id
    v.bank_name=bank_name
    v.bank_ifsc=bank_ifsc
    v.bank_account=bank_account
    v.is_deleted = False
    db.session.commit()
    flash("Vendor Updated — ledger Updated under Sundry Creditors.", "success")
    return redirect(url_for('vendors.vendors_list'))
