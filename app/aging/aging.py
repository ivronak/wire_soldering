# Sales S6 — Receivables aging: kis customer se kitna paisa lena hai aur wo kitne din se late hai.
# Judta hai: sales_invoices (due_date, outstanding), receipts (advance / On account), customers.ledger (tie-out ke liye).
#
# Rules (memory.md S6 decision):
#   * Sirf Posted invoice ka baaki paisa (outstanding) gina jata hai; Waiting / Cancelled nahi.
#   * Bucket = "as on" date tak due date se kitne din late: Not yet due (<=0) | 1-30 | 31-60 | 61-90 | 90+.
#   * Advance (On account) alag dikhta hai, buckets me minus nahi hota — owner ko dikhna chahiye ki kitna advance pada hai.
#   * "Other balance" = customer ledger ka wo hissa jo kisi invoice se nahi aaya (jaise purana opening balance). Isse
#     Net receivable hamesha customer ledger se match karta hai (tie-out).
from app.models import Customer
from app.receipts.collect import on_account_total, open_invoices

BUCKETS = ("current", "b1", "b2", "b3", "b4")
BUCKET_LABELS = {"current": "Not yet due", "b1": "1-30 days", "b2": "31-60 days", "b3": "61-90 days", "b4": "Over 90 days"}


def bucket_of(days_overdue):
    # days_overdue <= 0 matlab abhi due nahi hua
    if days_overdue <= 0:
        return "current"
    if days_overdue <= 30:
        return "b1"
    if days_overdue <= 60:
        return "b2"
    if days_overdue <= 90:
        return "b3"
    return "b4"


def build_aging(as_on):
    """Har customer ki row + grand total. Jinka kuch lena/advance/other nahi unko chhod dete hain."""
    rows = []
    totals = {key: 0.0 for key in BUCKETS}
    totals.update({"invoices": 0.0, "advance": 0.0, "other": 0.0, "net": 0.0})
    for customer in Customer.query.filter_by(is_deleted=False).order_by(Customer.name).all():
        buckets = {key: 0.0 for key in BUCKETS}
        lines = []
        for invoice in open_invoices(customer):
            late = invoice.days_overdue(as_on)
            key = bucket_of(late)
            buckets[key] += invoice.outstanding
            lines.append({"no": invoice.invoice_no, "date": invoice.invoice_date, "due": invoice.due_on, "total": invoice.total_amount,
                          "paid": invoice.paid, "outstanding": invoice.outstanding, "late": late, "bucket": key})
        invoices_total = round(sum(buckets.values()), 2)
        advance = on_account_total(customer)
        owed_by_ledger = round(-(customer.ledger.current_balance if customer.ledger else 0), 2)
        # Ledger me jo hai - (invoice ka baaki - advance) = bina-invoice ka hissa (opening balance waghera)
        other = round(owed_by_ledger - (invoices_total - advance), 2)
        if abs(invoices_total) < 0.005 and abs(advance) < 0.005 and abs(other) < 0.005:
            continue
        row = {"id": customer.id, "name": customer.name, "invoices": invoices_total, "advance": advance, "other": other,
               "net": owed_by_ledger, "lines": lines, "oldest": max((ln["late"] for ln in lines), default=None)}
        row.update({key: round(value, 2) for key, value in buckets.items()})
        rows.append(row)
        for key in BUCKETS:
            totals[key] += row[key]
        totals["invoices"] += invoices_total
        totals["advance"] += advance
        totals["other"] += other
        totals["net"] += owed_by_ledger
    totals = {key: round(value, 2) for key, value in totals.items()}
    # Sabse zyada late wala customer upar (overdue paisa zyada = pehle dikhe)
    rows.sort(key=lambda r: (-(r["b4"] + r["b3"] + r["b2"] + r["b1"]), r["name"].lower()))
    return rows, totals
