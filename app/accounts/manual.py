# Accounts A6: hath se banaye voucher (Payment, Receipt, Journal, Contra) + unka reverse.
# Auto-posting wale voucher (invoice, receipt...) yahan se reverse nahi hote — unka document cancel karo (A3 / A4 / A5).
# Party ledger (Customer / Vendor) ki line ho to Ledger.current_balance bhi saath me badalta hai (Cr plus / Dr minus), taaki aging / statement / tally match rahe.
from app.accounts.posting import VoucherError, post_voucher, reverse_voucher
from app.models import ChartOfAccountsGroup, Ledger

MANUAL_TYPES = ("Payment", "Receipt", "Journal", "Contra")
MANUAL_SOURCE = "manual"
PARTY_GROUPS = ("Sundry Debtors", "Sundry Creditors")
CASH_BANK_GROUPS = ("Cash-in-hand", "Bank Accounts")


def is_party(ledger):
    return ledger.group is not None and ledger.group.name in PARTY_GROUPS


def is_cash_bank(ledger):
    return ledger.group is not None and ledger.group.name in CASH_BANK_GROUPS


def sync_party_balances(entries):
    # entries = [(ledger, side, amount)] ya VoucherEntry — party ledger ka current_balance usi hisaab se (Cr plus, Dr minus)
    for entry in entries:
        ledger, side, amount = entry if isinstance(entry, tuple) else (entry.ledger, entry.side, entry.amount)
        if is_party(ledger):
            ledger.current_balance = round(ledger.current_balance + (amount if side == "Cr" else -amount), 2)


def _check_rules(voucher_type, lines):
    cash_dr = any(is_cash_bank(l) and s == "Dr" for l, s, _a in lines)
    cash_cr = any(is_cash_bank(l) and s == "Cr" for l, s, _a in lines)
    if voucher_type == "Payment" and not cash_cr:
        raise VoucherError("A Payment voucher needs a Cash or Bank ledger on the credit side (money going out).")
    if voucher_type == "Receipt" and not cash_dr:
        raise VoucherError("A Receipt voucher needs a Cash or Bank ledger on the debit side (money coming in).")
    if voucher_type == "Contra" and not all(is_cash_bank(l) for l, _s, _a in lines):
        raise VoucherError("A Contra voucher can only use Cash and Bank ledgers (moving money between them).")
    if voucher_type == "Journal" and any(is_cash_bank(l) for l, _s, _a in lines):
        raise VoucherError("A Journal voucher cannot use Cash or Bank ledgers. Use Payment, Receipt or Contra.")


def post_manual(voucher_type, voucher_date, lines, narration, created_by_id=None):
    """lines = [(ledger, 'Dr'/'Cr', amount)]. Rules check -> voucher -> party balance sync. Commit caller karta hai. VoucherError par message user ko dikha sakte hain."""
    if voucher_type not in MANUAL_TYPES:
        raise VoucherError("Choose a voucher type.")
    _check_rules(voucher_type, lines)
    voucher = post_voucher(voucher_type, voucher_date, lines, narration=narration, source_type=MANUAL_SOURCE, created_by_id=created_by_id)
    sync_party_balances(lines)
    return voucher


def reverse_manual(voucher, reason, voucher_date=None, created_by_id=None):
    if voucher.source_type != MANUAL_SOURCE:
        raise VoucherError("Only a manual voucher can be reversed here. Cancel the original document instead.")
    reversal = reverse_voucher(voucher, reason, voucher_date=voucher_date, created_by_id=created_by_id)
    sync_party_balances(reversal.entries)
    return reversal


def pickable_ledgers():
    # Voucher me chunne layak ledger: active, group ke hisaab se sorted
    return (Ledger.query.join(ChartOfAccountsGroup, Ledger.group_id == ChartOfAccountsGroup.id)
            .filter(Ledger.is_active == True)       # noqa: E712
            .order_by(ChartOfAccountsGroup.name, Ledger.name).all())
