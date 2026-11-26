# Accounts A2: party (Customer / Vendor) ledger ka opening balance voucher se likhna + purane balance ka backfill + tally.
# Idea: ledger ka "pichhla sab kuch" ek Opening voucher me jaata hai: party ledger ek taraf, system ledger "Opening Balance Adjustment" doosri taraf.
# Sign rule (project): current_balance me Cr = plus, Dr = minus. Plus balance (vendor ko dena / customer ka advance) = party ledger Cr;
# minus balance (customer se lena) = party ledger Dr.
# Purane documents (invoice / receipt / bill) ko dobara post NAHI karte — sirf unka natija (current_balance) ek opening voucher me aata hai,
# warna double count ho jaata. A3 / A4 se naye documents khud voucher banayenge. Flow doc: accounts_flow_2026_11_25.md §7.
from datetime import date

from app.accounts.posting import paise, post_voucher, system_ledger
from app.models import ChartOfAccountsGroup, Ledger, VoucherEntry

SOURCE = "ledger_opening"


def post_opening(ledger, signed_amount, voucher_date=None, created_by_id=None, narration=None):
    """signed_amount = Cr plus / Dr minus. Zero ho to kuch nahi banta (None). Voucher lautata hai, commit caller karta hai."""
    cents = paise(signed_amount)
    if cents == 0:
        return None
    counter = system_ledger("opening_balance")
    party_side, counter_side = ("Cr", "Dr") if cents > 0 else ("Dr", "Cr")
    amount = abs(cents) / 100
    return post_voucher("Opening", voucher_date or date.today(), [(ledger, party_side, amount), (counter, counter_side, amount)],
                        narration=narration or "Opening balance - %s" % ledger.name, source_type=SOURCE, source_id=ledger.id,
                        created_by_id=created_by_id)


def party_ledgers():
    # Customer / Vendor ke apne ledger = Sundry Debtors / Sundry Creditors group me (A3 ke baad bank ledger bhi system_key ke bina bante hain, wo party nahi)
    return (Ledger.query.join(ChartOfAccountsGroup, Ledger.group_id == ChartOfAccountsGroup.id)
            .filter(Ledger.is_system == False, Ledger.system_key.is_(None), ChartOfAccountsGroup.name.in_(("Sundry Debtors", "Sundry Creditors")))   # noqa: E712
            .order_by(Ledger.id).all())


def entries_balance(ledger):
    # Sirf vouchers se balance (Cr plus, Dr minus), rupees me (paise ke integer se jod ke)
    total = 0
    for entry in VoucherEntry.query.filter_by(ledger_id=ledger.id).all():
        total += paise(entry.amount) if entry.side == "Cr" else -paise(entry.amount)
    return total / 100


def backfill(voucher_date=None, created_by_id=None):
    """Har party ledger me (current_balance - vouchers ka balance) ka FARAK Opening voucher me daalo. Pehli baar ye poora purana balance hota hai;
    agar ledger ke paas pehle se opening entry thi (naya party, A2 ke baad bana) to sirf bacha hua hissa. Dobara chalao to farak 0 = kuch nahi banta,
    isliye double nahi hota. (kitne voucher bane, kitne ledger pehle se barabar) lautata hai."""
    made = skipped = 0
    for ledger in party_ledgers():
        gap = paise(ledger.current_balance) - paise(entries_balance(ledger))
        if gap == 0:
            skipped += 1
            continue
        post_opening(ledger, gap / 100, voucher_date=voucher_date, created_by_id=created_by_id,
                     narration="Opening balance carried from existing records - %s" % ledger.name)
        made += 1
    return made, skipped


def tally():
    """Har party ledger: vouchers ka balance vs purana current_balance. Farak wali list lautata hai [(ledger, entries, current, diff)].
    A3 / A4 tak naye invoice / receipt abhi voucher nahi banate, isliye backfill ke baad naye documents par farak aana swabhavik hai."""
    rows = []
    for ledger in party_ledgers():
        from_entries = entries_balance(ledger)
        diff = round(from_entries - ledger.current_balance, 2)
        if abs(diff) >= 0.005:
            rows.append((ledger, from_entries, ledger.current_balance, diff))
    return rows
