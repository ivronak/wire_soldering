# Sales S5 — Receipt (customer se paisa milna): invoice ke against allocation (bill-by-bill), baaki "On account", customer ledger me Cr.
# Judta hai: sales_invoices (kitna lena baaki), customers.ledger (current_balance), payment_modes master.
#
# Rules (memory.md S5 decision):
#   * Ledger sign rule (project): Cr = plus, Dr = minus. Invoice se customer ledger minus gaya tha (lena); receipt se wapas plus (lena kam).
#   * Ek receipt kai invoices ke against ho sakti hai. Jo allocate nahi hua wo On account (advance) — baad me kisi invoice se jod sakte hain.
#   * Sirf Posted invoice ke against, aur us invoice ke baaki (outstanding) se zyada nahi.
#   * Cancel = ledger wapas + allocations khatam (invoice phir unpaid / part paid). Receipt ki row delete nahi hoti.
#   * Bank / cash ledger me Dr abhi nahi (Accounting phase me vouchers aayenge — tab sirf yahi file badlegi).
from datetime import datetime

from app.extensions import db
from app.models import Quotation, SalesInvoice, SalesReceipt, SalesReceiptAllocation

TOLERANCE = 0.005


class ReceiptError(Exception):
    pass


def next_receipt_no(receipt_date):
    # RC-<saal>-<agla number>: sabse bada number dekhte hain (count nahi), taaki gap hone par bhi number repeat na ho
    prefix = f"RC-{receipt_date.year}-"
    last = 0
    for (number,) in db.session.query(SalesReceipt.receipt_no).filter(SalesReceipt.receipt_no.like(prefix + "%")).all():
        try:
            last = max(last, int(number.split("-")[-1]))
        except ValueError:
            pass
    return f"{prefix}{last + 1:03d}"


def open_invoices(customer):
    # Customer ke Posted invoices jinka paisa baaki hai (purana pehle)
    rows = (SalesInvoice.query.join(Quotation, Quotation.id == SalesInvoice.quotation_id)
            .filter(Quotation.customer_id == customer.id, SalesInvoice.status == "Posted", SalesInvoice.is_deleted == False)
            .order_by(SalesInvoice.invoice_date, SalesInvoice.id).all())
    return [inv for inv in rows if inv.outstanding > TOLERANCE]


def on_account_total(customer):
    # Customer ke Posted receipts ka bina-invoice wala (advance) paisa
    total = 0.0
    for receipt in SalesReceipt.query.filter_by(customer_id=customer.id, status="Posted", is_deleted=False).all():
        total += receipt.on_account
    return round(total, 2)


def _check_alloc(customer, alloc, limit):
    """alloc = {invoice_id: amount}. Har invoice customer ka, Posted, baaki se zyada nahi; jod limit se zyada nahi. Saaf list [(invoice, amount)] deta hai."""
    picked = []
    total = 0.0
    for invoice_id, amount in alloc.items():
        if amount < 0:
            raise ReceiptError("An amount against an invoice cannot be negative.")
        if amount <= TOLERANCE:
            continue
        invoice = db.session.get(SalesInvoice, invoice_id)
        if invoice is None or invoice.is_deleted or invoice.quotation.customer_id != customer.id:
            raise ReceiptError("An invoice does not belong to this customer.")
        if invoice.status != "Posted":
            raise ReceiptError(f"Invoice {invoice.invoice_no} is not posted, so it cannot be paid yet.")
        if amount > invoice.outstanding + TOLERANCE:
            raise ReceiptError(f"Invoice {invoice.invoice_no}: only ₹{invoice.outstanding:,.2f} is due, but ₹{amount:,.2f} was entered.")
        picked.append((invoice, round(amount, 2)))
        total += amount
    if total > limit + TOLERANCE:
        raise ReceiptError(f"The amount applied to invoices (₹{total:,.2f}) is more than the money available (₹{limit:,.2f}).")
    return picked


def create_receipt(customer, receipt_date, amount, mode, reference, notes, alloc):
    """Receipt + allocations banata hai, customer ledger me Cr. Galti par ReceiptError (caller rollback karta hai)."""
    if amount <= TOLERANCE:
        raise ReceiptError("Enter an amount greater than zero.")
    if mode is None or not mode.is_active or mode.is_deleted:
        raise ReceiptError("Choose a payment mode.")
    picked = _check_alloc(customer, alloc, amount)
    receipt = SalesReceipt(receipt_no=next_receipt_no(receipt_date), customer_id=customer.id, receipt_date=receipt_date, amount=round(amount, 2),
                           payment_mode_id=mode.id, reference=reference, notes=notes, status="Posted")
    db.session.add(receipt)
    db.session.flush()
    for invoice, part in picked:
        db.session.add(SalesReceiptAllocation(receipt_id=receipt.id, invoice_id=invoice.id, amount=part))
    ledger = customer.ledger
    ledger.current_balance = round(ledger.current_balance + receipt.amount, 2)      # Cr: lena kam
    db.session.flush()
    return receipt


def allocate_more(receipt, alloc):
    """Receipt ke On account hisse ko ab invoices ke against lagao."""
    if receipt.status != "Posted":
        raise ReceiptError("This receipt is cancelled.")
    picked = _check_alloc(receipt.customer, alloc, receipt.on_account)
    if not picked:
        raise ReceiptError("Enter an amount against at least one invoice.")
    for invoice, part in picked:
        db.session.add(SalesReceiptAllocation(receipt_id=receipt.id, invoice_id=invoice.id, amount=part))
    db.session.flush()
    return picked


def cancel_receipt(receipt, reason):
    """Receipt cancel: customer ledger wapas (lena phir badha), allocations khatam (invoice phir baaki)."""
    if receipt.status == "Cancelled":
        raise ReceiptError("This receipt is already cancelled.")
    ledger = receipt.customer.ledger
    ledger.current_balance = round(ledger.current_balance - receipt.amount, 2)
    receipt.status = "Cancelled"
    receipt.cancel_reason = reason
    receipt.cancelled_at = datetime.utcnow()
    db.session.flush()
