# Accounts A5 — Payables aging: kis vendor ko kitna dena hai aur bill kitne din se late hai (receivables aging ka mirror).
# Bucket = "as on" date tak due date se kitne din late. Due date = bill date + vendor payment terms ke days.
# "Other" = vendor ledger ka wo hissa jo kisi bill se nahi aaya (purana opening balance waghera) — isse Net payable hamesha vendor ledger se match karta hai.
from app.aging.aging import BUCKETS, BUCKET_LABELS, bucket_of  # noqa: F401  (same buckets receivables jaise)
from app.models import Vendor
from app.vendor_payments.collect import on_account_total, open_bills


def build_payables(as_on):
    rows = []
    totals = {key: 0.0 for key in BUCKETS}
    totals.update({"bills": 0.0, "advance": 0.0, "other": 0.0, "net": 0.0})
    for vendor in Vendor.query.filter_by(is_deleted=False).order_by(Vendor.name).all():
        buckets = {key: 0.0 for key in BUCKETS}
        lines = []
        for bill in open_bills(vendor):
            late = bill.days_overdue(as_on)
            key = bucket_of(late)
            buckets[key] += bill.outstanding
            lines.append({"no": bill.pi_no, "vendor_no": bill.vendor_invoice_no, "date": bill.invoice_date, "due": bill.due_on,
                          "total": bill.total_amount, "paid": bill.paid, "outstanding": bill.outstanding, "late": late, "bucket": key})
        bills_total = round(sum(buckets.values()), 2)
        advance = on_account_total(vendor)
        owed_by_ledger = round(vendor.ledger.current_balance if vendor.ledger else 0, 2)      # vendor: Cr plus = hume dena
        other = round(owed_by_ledger - (bills_total - advance), 2)
        if abs(bills_total) < 0.005 and abs(advance) < 0.005 and abs(other) < 0.005:
            continue
        row = {"id": vendor.id, "name": vendor.name, "bills": bills_total, "advance": advance, "other": other, "net": owed_by_ledger,
               "lines": lines, "oldest": max((ln["late"] for ln in lines), default=None)}
        row.update({key: round(value, 2) for key, value in buckets.items()})
        rows.append(row)
        for key in BUCKETS:
            totals[key] += row[key]
        totals["bills"] += bills_total
        totals["advance"] += advance
        totals["other"] += other
        totals["net"] += owed_by_ledger
    totals = {key: round(value, 2) for key, value in totals.items()}
    rows.sort(key=lambda r: (-(r["b4"] + r["b3"] + r["b2"] + r["b1"]), r["name"].lower()))
    return rows, totals
