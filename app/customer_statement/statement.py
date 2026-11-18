# Sales S8 — Customer statement: ek customer ke invoices, receipts aur credit notes ek list me, running balance ke saath.
# Judta hai: sales_invoices, sales_receipts, sales_returns aur customers.ledger (closing balance ledger se match hona chahiye).
#
# Rules (memory.md S8 decision):
#   * Ledger sign rule (project): Cr = plus, Dr = minus. Statement me customer ke nazariye se: Debit = invoice (hume lena badha),
#     Credit = receipt / credit note (lena kam). Balance "Dr" = customer ko dena hai, "Cr" = hume customer ko dena / advance.
#   * Sirf Posted documents. Cancelled / Waiting approval nahi (unka asar ledger me hai hi nahi).
#   * Opening (period ka shuru) = customer ka opening balance + period se pehle ke documents. Agar ledger me kuch aisa ho jo
#     sales documents se nahi aaya ("other"), wo opening me jod diya jata hai taaki closing hamesha ledger se mile.
#   * Accounting phase aane par ye report ledger ke vouchers se chalegi; abhi ye sales documents se banti hai.
from app.models import Quotation, SalesInvoice, SalesReceipt, SalesReturn

# Ek din ke andar ka order: pehle invoice, phir credit note, phir receipt
ORDER = {"Invoice": 0, "Credit note": 1, "Receipt": 2}


def _documents(customer):
    docs = []
    invoices = (SalesInvoice.query.join(Quotation, Quotation.id == SalesInvoice.quotation_id)
                .filter(Quotation.customer_id == customer.id, SalesInvoice.status == "Posted", SalesInvoice.is_deleted == False).all())
    for inv in invoices:
        po = f" · Customer PO {inv.quotation.customer_po_no}" if inv.quotation.customer_po_no else ""
        docs.append({"date": inv.invoice_date, "type": "Invoice", "id": inv.id, "ref": inv.invoice_no, "text": f"Tax invoice · {inv.quotation.quote_no}{po}",
                     "debit": inv.total_amount, "credit": 0.0})
    for rc in SalesReceipt.query.filter_by(customer_id=customer.id, status="Posted", is_deleted=False).all():
        text = f"Receipt · {rc.payment_mode.name}" + (f" · {rc.reference}" if rc.reference else "")
        if rc.on_account > 0.004:
            text += f" · ₹{rc.on_account:,.2f} on account"
        docs.append({"date": rc.receipt_date, "type": "Receipt", "id": rc.id, "ref": rc.receipt_no, "text": text, "debit": 0.0, "credit": rc.amount})
    returns = (SalesReturn.query.join(SalesInvoice, SalesInvoice.id == SalesReturn.invoice_id).join(Quotation, Quotation.id == SalesInvoice.quotation_id)
               .filter(Quotation.customer_id == customer.id, SalesReturn.status == "Posted", SalesReturn.is_deleted == False).all())
    for sr in returns:
        docs.append({"date": sr.return_date, "type": "Credit note", "id": sr.id, "ref": sr.return_no, "text": f"Goods returned against {sr.invoice.invoice_no} · {sr.reason}",
                     "debit": 0.0, "credit": sr.total_amount})
    docs.sort(key=lambda d: (d["date"], ORDER[d["type"]], d["id"]))
    return docs


def build_statement(customer, date_from, date_to):
    """{opening, rows, closing, debit_total, credit_total, other, ledger_balance, matches}. Balance sab 'receivable' nazariye se:
    + = customer ko dena hai (Dr), - = customer ka credit (Cr)."""
    ledger = customer.ledger
    opening_signed = 0.0
    if ledger is not None:
        opening_signed = ledger.opening_balance if ledger.opening_balance_type == "Cr" else -ledger.opening_balance
    current = ledger.current_balance if ledger is not None else 0.0
    docs = _documents(customer)
    all_signed = sum(d["credit"] - d["debit"] for d in docs)
    other = round(current - (opening_signed + all_signed), 2)       # sales documents ke bahar ka asar (normally 0)

    owed = -(opening_signed + other)                               # receivable nazariya
    rows, debit_total, credit_total = [], 0.0, 0.0
    for d in docs:
        if d["date"] < date_from:
            owed += d["debit"] - d["credit"]
    opening = round(owed, 2)
    for d in docs:
        if date_from <= d["date"] <= date_to:
            owed += d["debit"] - d["credit"]
            debit_total += d["debit"]
            credit_total += d["credit"]
            rows.append(dict(d, balance=round(owed, 2)))
    closing = round(owed, 2)
    after = any(d["date"] > date_to for d in docs)
    return {"opening": opening, "rows": rows, "closing": closing, "debit_total": round(debit_total, 2), "credit_total": round(credit_total, 2),
            "other": other, "ledger_owed": round(-current, 2), "complete": not after,
            "matches": (not after) and abs(closing - round(-current, 2)) < 0.011}
