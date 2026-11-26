# Accounts A3: Sales side ke documents (Receipt, Sales invoice, Sales return) ko voucher me likhna.
# Purane modules (billing.py, collect.py, returns.py) ab bhi Ledger.current_balance badlate hain (tally ke liye), saath me yahan se voucher banta hai.
# Cancel = naya ulta voucher (reverse_voucher), purana voucher "Reversed" ho jaata hai — kuch delete nahi.
# Sign rule: party ledger me customer ka lena = Dr. Flow doc: accounts_flow_2026_11_25.md §4.
from datetime import date

from app.accounts.posting import VoucherError, post_voucher, reverse_voucher, system_ledger
from app.extensions import db
from app.models import ChartOfAccountsGroup, FGMovement, Ledger, Voucher
from app.tax import split_tax

SRC_INVOICE = "sales_invoice"
SRC_RECEIPT = "sales_receipt"
SRC_RETURN = "sales_return"
SRC_PURCHASE = "purchase_invoice"
SRC_PURCHASE_RETURN = "purchase_return"


def _add(lines, ledger, side, amount):
    # Zero amount ki line voucher me nahi jaati (post_voucher zero reject karta hai); minus amount ho to side ulti
    cents = round(float(amount) * 100)
    if cents == 0:
        return
    if cents < 0:
        side = "Cr" if side == "Dr" else "Dr"
    lines.append((ledger, side, abs(cents) / 100))


def _post(voucher_type, voucher_date, lines, **kw):
    # Zero-value document (sab amount 0) me voucher ki zaroorat nahi — None lautata hai
    if len(lines) < 2:
        return None
    return post_voucher(voucher_type, voucher_date, lines, **kw)


def ledger_for_mode(mode):
    """Payment mode ka ledger. 'cash' naam wala mode = system Cash ledger; baaki har mode ka apna ledger Bank Accounts group me (pehli baar bante hi ban jaata hai)."""
    if mode.ledger_id:
        return mode.ledger
    if "cash" in (mode.name or "").lower():
        ledger = system_ledger("cash")
    else:
        group = ChartOfAccountsGroup.query.filter_by(name="Bank Accounts").first()
        if group is None:
            raise VoucherError("The 'Bank Accounts' group is missing from the chart of accounts.")
        ledger = Ledger(name=mode.name, group_id=group.id, opening_balance=0, opening_balance_type="Dr", current_balance=0)
        db.session.add(ledger)
        db.session.flush()
    mode.ledger_id = ledger.id
    db.session.flush()
    return ledger


def _live_voucher(source_type, source_id):
    # Is document ka abhi chalu (Posted, reversal nahi) voucher
    return (Voucher.query.filter_by(source_type=source_type, source_id=source_id, status="Posted", reverses_voucher_id=None)
            .order_by(Voucher.id.desc()).first())


def reverse_for(source_type, source_id, reason, created_by_id=None, voucher_date=None):
    """Document cancel hone par uska voucher ulta. Voucher na mile (A3 se pehle ka document) to chupchap kuch nahi — uska asar opening voucher me hai."""
    voucher = _live_voucher(source_type, source_id)
    if voucher is None:
        return None
    return reverse_voucher(voucher, reason, voucher_date=voucher_date or date.today(), created_by_id=created_by_id)


def post_receipt(receipt, created_by_id=None):
    """Receipt: Dr Cash / Bank (payment mode ka ledger), Cr Customer."""
    bank = ledger_for_mode(receipt.payment_mode)
    lines = []
    _add(lines, bank, "Dr", receipt.amount)
    _add(lines, receipt.customer.ledger, "Cr", receipt.amount)
    return _post("Receipt", receipt.receipt_date, lines, narration="Receipt %s - %s" % (receipt.receipt_no, receipt.customer.name),
                        source_type=SRC_RECEIPT, source_id=receipt.id, created_by_id=created_by_id)


def post_sales_invoice(invoice, created_by_id=None):
    """Invoice Posted: Dr Customer (total); Cr Sales (subtotal), Charges, Output GST (CGST+SGST ya IGST), Round-off (agar farak).
    Saath me COGS: Dr Cost of goods sold, Cr Stock-in-hand (cost_total). Ek hi voucher, Dr = Cr."""
    customer = invoice.quotation.customer
    lines = []
    _add(lines, customer.ledger, "Dr", invoice.total_amount)
    _add(lines, system_ledger("sales"), "Cr", invoice.subtotal)
    _add(lines, system_ledger("sales_charges"), "Cr", invoice.charges_total)          # minus charges ho to apne aap Dr
    if invoice.tax_type == "inter":
        _add(lines, system_ledger("output_igst"), "Cr", invoice.tax_total)
    else:
        cgst, sgst = split_tax(invoice.tax_total)
        _add(lines, system_ledger("output_cgst"), "Cr", cgst)
        _add(lines, system_ledger("output_sgst"), "Cr", sgst)
    # Paise ka farak (float) round-off me jaata hai taaki voucher hamesha balanced rahe
    credit_side = round(invoice.subtotal + invoice.charges_total + invoice.tax_total, 2)
    _add(lines, system_ledger("round_off"), "Cr", round(invoice.total_amount - credit_side, 2))
    _add(lines, system_ledger("cogs"), "Dr", invoice.cost_total)
    _add(lines, system_ledger("stock_in_hand"), "Cr", invoice.cost_total)
    return _post("Sales", invoice.invoice_date, lines, narration="Sales invoice %s - %s" % (invoice.invoice_no, customer.name),
                        source_type=SRC_INVOICE, source_id=invoice.id, created_by_id=created_by_id)


def _returned_stock_value(ret):
    # Sirf achha maal jo wapas stock me gaya (kharab maal stock me nahi aata, uski cost COGS me hi rehti hai)
    total = 0.0
    for move in FGMovement.query.filter_by(ref_type="SR", ref_id=ret.id, movement_type="SALES_RETURN").all():
        if move.reverses_movement_id is None and move.qty > 0:
            total += move.value or 0
    return round(total, 2)


def post_sales_return(ret, created_by_id=None):
    """Credit note: Dr Sales Return (subtotal) + Output GST ulta; Cr Customer (total). COGS ulta: Dr Stock-in-hand, Cr COGS (wapas aaye achhe maal ki cost)."""
    customer = ret.invoice.quotation.customer
    lines = []
    _add(lines, customer.ledger, "Cr", ret.total_amount)
    _add(lines, system_ledger("sales_return"), "Dr", ret.subtotal)
    if ret.invoice.tax_type == "inter":
        _add(lines, system_ledger("output_igst"), "Dr", ret.tax_total)
    else:
        cgst, sgst = split_tax(ret.tax_total)
        _add(lines, system_ledger("output_cgst"), "Dr", cgst)
        _add(lines, system_ledger("output_sgst"), "Dr", sgst)
    debit_side = round(ret.subtotal + ret.tax_total, 2)
    _add(lines, system_ledger("round_off"), "Dr", round(ret.total_amount - debit_side, 2))
    stock_value = _returned_stock_value(ret)
    _add(lines, system_ledger("stock_in_hand"), "Dr", stock_value)
    _add(lines, system_ledger("cogs"), "Cr", stock_value)
    return _post("Credit note", ret.return_date, lines, narration="Credit note %s - %s" % (ret.return_no, customer.name),
                        source_type=SRC_RETURN, source_id=ret.id, created_by_id=created_by_id)


def post_purchase_invoice(invoice, created_by_id=None):
    """Bill Posted: Dr Stock-in-hand (subtotal + charges: perpetual, maal stock me aaya), Dr Input GST (CGST+SGST ya IGST); Cr Vendor (total).
    Round-off farak me. Minus charges ho to apne aap Cr."""
    vendor = invoice.vendor
    lines = []
    _add(lines, vendor.ledger, "Cr", invoice.total_amount)
    _add(lines, system_ledger("stock_in_hand"), "Dr", invoice.subtotal)
    _add(lines, system_ledger("purchase_charges"), "Dr", invoice.charges_total)
    if invoice.tax_type == "inter":
        _add(lines, system_ledger("input_igst"), "Dr", invoice.tax_total)
    else:
        cgst, sgst = split_tax(invoice.tax_total)
        _add(lines, system_ledger("input_cgst"), "Dr", cgst)
        _add(lines, system_ledger("input_sgst"), "Dr", sgst)
    debit_side = round(invoice.subtotal + invoice.charges_total + invoice.tax_total, 2)
    _add(lines, system_ledger("round_off"), "Dr", round(invoice.total_amount - debit_side, 2))
    return _post("Purchase", invoice.invoice_date, lines, narration="Purchase bill %s (%s) - %s" % (invoice.pi_no, invoice.vendor_invoice_no, vendor.name),
                 source_type=SRC_PURCHASE, source_id=invoice.id, created_by_id=created_by_id)


def post_purchase_return(ret, created_by_id=None):
    """Purchase return (debit note): Dr Vendor (total); Cr Stock-in-hand (subtotal + charges), Cr Input GST. Bill ke ulta."""
    vendor = ret.invoice.vendor
    lines = []
    _add(lines, vendor.ledger, "Dr", ret.total_amount)
    _add(lines, system_ledger("stock_in_hand"), "Cr", ret.subtotal)
    _add(lines, system_ledger("purchase_charges"), "Cr", ret.charges_total)
    if ret.invoice.tax_type == "inter":
        _add(lines, system_ledger("input_igst"), "Cr", ret.tax_total)
    else:
        cgst, sgst = split_tax(ret.tax_total)
        _add(lines, system_ledger("input_cgst"), "Cr", cgst)
        _add(lines, system_ledger("input_sgst"), "Cr", sgst)
    credit_side = round(ret.subtotal + ret.charges_total + ret.tax_total, 2)
    _add(lines, system_ledger("round_off"), "Cr", round(ret.total_amount - credit_side, 2))
    return _post("Debit note", ret.return_date, lines, narration="Debit note %s - %s" % (ret.pr_no, vendor.name),
                 source_type=SRC_PURCHASE_RETURN, source_id=ret.id, created_by_id=created_by_id)


SRC_VENDOR_PAYMENT = "vendor_payment"


def post_vendor_payment(payment, created_by_id=None):
    """Vendor ko payment: Dr Vendor (dena kam), Cr Cash / Bank (payment mode ka ledger)."""
    bank = ledger_for_mode(payment.payment_mode)
    lines = []
    _add(lines, payment.vendor.ledger, "Dr", payment.amount)
    _add(lines, bank, "Cr", payment.amount)
    return _post("Payment", payment.payment_date, lines, narration="Payment %s - %s" % (payment.payment_no, payment.vendor.name),
                 source_type=SRC_VENDOR_PAYMENT, source_id=payment.id, created_by_id=created_by_id)
