# Accounts A5 — Vendor payment (vendor ko paisa dena): bill ke against allocation (bill-by-bill), baaki "On account" (advance).
# Receipt (app/receipts/collect.py) ka mirror. Vendor ledger me Dr (current_balance minus ki taraf = dena kam) + Payment voucher (autopost).
# Cancel = ledger wapas + ulta voucher + allocations khatam. Row delete nahi hoti.
from datetime import datetime

from app.accounts.autopost import SRC_VENDOR_PAYMENT, post_vendor_payment, reverse_for
from app.auth import service as auth_service
from app.extensions import db
from app.models import PurchaseInvoice, VendorPayment, VendorPaymentAllocation

TOLERANCE = 0.005


class PaymentError(Exception):
    pass


def next_payment_no(payment_date):
    # VP-<saal>-<agla number>: sabse bada number dekhte hain (gap hone par bhi repeat nahi)
    prefix = f"VP-{payment_date.year}-"
    last = 0
    for (number,) in db.session.query(VendorPayment.payment_no).filter(VendorPayment.payment_no.like(prefix + "%")).all():
        try:
            last = max(last, int(number.split("-")[-1]))
        except ValueError:
            pass
    return f"{prefix}{last + 1:03d}"


def open_bills(vendor):
    # Vendor ke Posted bills jinka paisa dena baaki hai (purana pehle)
    rows = (PurchaseInvoice.query.filter_by(vendor_id=vendor.id, status="Posted", is_deleted=False)
            .order_by(PurchaseInvoice.invoice_date, PurchaseInvoice.id).all())
    return [bill for bill in rows if bill.outstanding > TOLERANCE]


def on_account_total(vendor):
    # Vendor ko diya hua bina-bill wala (advance) paisa
    return round(sum(p.on_account for p in VendorPayment.query.filter_by(vendor_id=vendor.id, status="Posted", is_deleted=False).all()), 2)


def _check_alloc(vendor, alloc, limit):
    picked, total = [], 0.0
    for invoice_id, amount in alloc.items():
        if amount < 0:
            raise PaymentError("An amount against a bill cannot be negative.")
        if amount <= TOLERANCE:
            continue
        bill = db.session.get(PurchaseInvoice, invoice_id)
        if bill is None or bill.is_deleted or bill.vendor_id != vendor.id:
            raise PaymentError("A bill does not belong to this vendor.")
        if bill.status != "Posted":
            raise PaymentError(f"Bill {bill.pi_no} is not posted, so it cannot be paid yet.")
        if amount > bill.outstanding + TOLERANCE:
            raise PaymentError(f"Bill {bill.pi_no}: only ₹{bill.outstanding:,.2f} is due, but ₹{amount:,.2f} was entered.")
        picked.append((bill, round(amount, 2)))
        total += amount
    if total > limit + TOLERANCE:
        raise PaymentError(f"The amount applied to bills (₹{total:,.2f}) is more than the payment (₹{limit:,.2f}).")
    return picked


def create_payment(vendor, payment_date, amount, mode, reference, notes, alloc):
    """Payment + allocations banata hai, vendor ledger me Dr + voucher. Galti par PaymentError (caller rollback karta hai)."""
    if amount <= TOLERANCE:
        raise PaymentError("Enter an amount greater than zero.")
    if mode is None or not mode.is_active or mode.is_deleted:
        raise PaymentError("Choose a payment mode.")
    if vendor.ledger is None:
        raise PaymentError("This vendor has no ledger.")
    picked = _check_alloc(vendor, alloc, amount)
    payment = VendorPayment(payment_no=next_payment_no(payment_date), vendor_id=vendor.id, payment_date=payment_date, amount=round(amount, 2),
                            payment_mode_id=mode.id, reference=reference, notes=notes, status="Posted", created_by_id=auth_service.actor_id())
    db.session.add(payment)
    db.session.flush()
    for bill, part in picked:
        db.session.add(VendorPaymentAllocation(payment_id=payment.id, invoice_id=bill.id, amount=part))
    ledger = vendor.ledger
    ledger.current_balance = round(ledger.current_balance - payment.amount, 2)      # Dr: dena kam
    db.session.flush()
    db.session.refresh(payment)
    post_vendor_payment(payment, created_by_id=auth_service.actor_id())
    return payment


def allocate_more(payment, alloc):
    """Payment ke On account hisse ko ab bills ke against lagao (voucher nahi badalta: paisa pehle hi vendor ko Dr ho chuka hai)."""
    if payment.status != "Posted":
        raise PaymentError("This payment is cancelled.")
    picked = _check_alloc(payment.vendor, alloc, payment.on_account)
    if not picked:
        raise PaymentError("Enter an amount against at least one bill.")
    for bill, part in picked:
        db.session.add(VendorPaymentAllocation(payment_id=payment.id, invoice_id=bill.id, amount=part))
    db.session.flush()
    return picked


def cancel_payment(payment, reason):
    if payment.status == "Cancelled":
        raise PaymentError("This payment is already cancelled.")
    ledger = payment.vendor.ledger
    ledger.current_balance = round(ledger.current_balance + payment.amount, 2)
    reverse_for(SRC_VENDOR_PAYMENT, payment.id, reason, created_by_id=auth_service.actor_id())
    payment.status = "Cancelled"
    payment.cancel_reason = reason
    payment.cancelled_at = datetime.utcnow()
    payment.cancelled_by_id = auth_service.actor_id()
    db.session.flush()
