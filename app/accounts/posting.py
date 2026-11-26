# Accounts A1: voucher banane ka EK hi raasta (aage ke steps me sales / purchase / receipt sab yahin se post honge).
# Rules: kam se kam 2 lines, har amount plus, ledger active, aur Sum(Dr) = Sum(Cr) paise tak (rounding se bachne ke liye paise = integer me tolte hain).
# Voucher / entries kabhi edit-delete nahi (models.py listener rokta hai) — galti ho to reverse_voucher() ulta voucher banata hai.
# Ledger.current_balance ko ye file chhoti nahi: A3 / A4 me jab har module yahin se post karega tab wo entries se aayega.
from datetime import date

from app.extensions import db
from app.models import Ledger, Voucher, VoucherEntry

VOUCHER_TYPES = {
    "Sales": "SV", "Receipt": "RV", "Payment": "PV", "Purchase": "PU",
    "Journal": "JV", "Contra": "CV", "Credit note": "CN", "Debit note": "DN", "Opening": "OP",
}


class VoucherError(ValueError):
    """Voucher galat hai (balance nahi, ledger band, amount galat...) — message seedha user ko dikha sakte hain."""


def paise(amount):
    return int(round(float(amount) * 100))


def system_ledger(key):
    # Auto-posting system ledger ko system_key se dhundhti hai (naam badle to bhi chale)
    ledger = Ledger.query.filter_by(system_key=key).first()
    if ledger is None:
        raise VoucherError("System ledger '%s' is missing from the chart of accounts." % key)
    return ledger


def next_voucher_no(voucher_type, voucher_date):
    prefix = VOUCHER_TYPES[voucher_type]
    stem = "%s-%d-" % (prefix, voucher_date.year)
    count = Voucher.query.filter(Voucher.voucher_no.like(stem + "%")).count()
    return "%s%04d" % (stem, count + 1)


def post_voucher(voucher_type, voucher_date, lines, narration=None, source_type=None, source_id=None, created_by_id=None, reverses=None, reversal_reason=None):
    """lines = [(ledger, "Dr" ya "Cr", amount), ...]. Valid ho to Voucher + entries session me add karke Voucher lautata hai
    (commit caller karta hai, taaki document aur uska voucher ek saath save / rollback ho)."""
    if voucher_type not in VOUCHER_TYPES:
        raise VoucherError("Unknown voucher type.")
    if not isinstance(voucher_date, date):
        raise VoucherError("Enter a valid voucher date.")
    if len(lines) < 2:
        raise VoucherError("A voucher needs at least two lines.")
    total_dr = total_cr = 0
    clean = []
    for ledger, side, amount in lines:
        if side not in ("Dr", "Cr"):
            raise VoucherError("Each line must be Dr or Cr.")
        if ledger is None or not ledger.is_active:
            raise VoucherError("A ledger in this voucher is missing or inactive.")
        cents = paise(amount)
        if cents <= 0:
            raise VoucherError("Amounts must be more than zero.")
        if side == "Dr":
            total_dr += cents
        else:
            total_cr += cents
        clean.append((ledger, side, cents))
    if total_dr != total_cr:
        raise VoucherError("Debit (%.2f) and credit (%.2f) are not equal." % (total_dr / 100, total_cr / 100))
    voucher = Voucher(voucher_no=next_voucher_no(voucher_type, voucher_date), voucher_type=voucher_type, voucher_date=voucher_date,
                      narration=(narration or "")[:255] or None, source_type=source_type, source_id=source_id, status="Posted",
                      reverses_voucher_id=reverses.id if reverses is not None else None, reversal_reason=reversal_reason,
                      created_by_id=created_by_id)
    db.session.add(voucher)
    for ledger, side, cents in clean:
        voucher.entries.append(VoucherEntry(ledger=ledger, side=side, amount=cents / 100))
    db.session.flush()
    return voucher


def reverse_voucher(voucher, reason, voucher_date=None, created_by_id=None):
    """Ulta voucher (Dr <-> Cr). Asli voucher status 'Reversed' ho jaata hai, dono dikhte rehte hain. Dobara ya reversal ko reverse nahi."""
    if voucher.status != "Posted":
        raise VoucherError("This voucher is already reversed.")
    if voucher.reverses_voucher_id is not None:
        raise VoucherError("A reversal voucher cannot be reversed.")
    reason = (reason or "").strip()
    if len(reason) < 3:
        raise VoucherError("Write the reason for reversing.")
    lines = [(e.ledger, "Cr" if e.side == "Dr" else "Dr", e.amount) for e in voucher.entries]
    reversal = post_voucher(voucher.voucher_type, voucher_date or date.today(), lines, narration="Reversal of %s: %s" % (voucher.voucher_no, reason),
                            source_type=voucher.source_type, source_id=voucher.source_id, created_by_id=created_by_id,
                            reverses=voucher, reversal_reason=reason)
    voucher.status = "Reversed"
    return reversal


def ledger_balance(ledger):
    """Ledger ka balance sirf vouchers se, project ke sign rule me (Cr = plus, Dr = minus).
    Opening balance ab apna Opening voucher hai (opening.py), isliye Ledger.opening_balance field yahan alag se NAHI jodte (double count hoga)."""
    total = 0
    for entry in VoucherEntry.query.filter_by(ledger_id=ledger.id).all():
        total += paise(entry.amount) if entry.side == "Cr" else -paise(entry.amount)
    return total / 100
