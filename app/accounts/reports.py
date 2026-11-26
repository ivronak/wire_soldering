# Accounts A7: reports ka hisaab — Trial Balance, Profit & Loss, Balance Sheet, Day book. Sab sirf voucher_entries se (Ledger.current_balance se nahi).
# Sign: balance = Dr - Cr (paise me). Asset / Expense ka natural side Dr, Liability / Equity / Income ka Cr.
# Group ki classification (ChartOfAccountsGroup.classification): ASSET / LIABILITY / EQUITY / INCOME / EXPENSE.
# Sab ka mool niyam: har voucher balanced hai, isliye Trial Balance me Dr = Cr aur Balance Sheet me Assets = Liabilities + Equity + Profit hamesha milta hai.
from sqlalchemy import func

from app.extensions import db
from app.models import ChartOfAccountsGroup, FGMovement, Ledger, StockMovement, Voucher, VoucherEntry

PARTY_GROUPS = ("Sundry Debtors", "Sundry Creditors")
DIRECT_GROUPS = ("Purchase Accounts", "Direct Expenses")       # P&L me gross profit tak


def _cents(value):
    return int(round(float(value or 0) * 100))


def movements(date_from=None, date_to=None):
    """{ledger_id: dr_minus_cr_paise} un voucher entries ka jo [date_from, date_to] me hain (date None = bandh nahi)."""
    query = (db.session.query(VoucherEntry.ledger_id, VoucherEntry.side, func.sum(VoucherEntry.amount))
             .join(Voucher, Voucher.id == VoucherEntry.voucher_id))
    if date_from is not None:
        query = query.filter(Voucher.voucher_date >= date_from)
    if date_to is not None:
        query = query.filter(Voucher.voucher_date <= date_to)
    out = {}
    for ledger_id, side, total in query.group_by(VoucherEntry.ledger_id, VoucherEntry.side).all():
        out[ledger_id] = out.get(ledger_id, 0) + (_cents(total) if side == "Dr" else -_cents(total))
    return out


def _ledger_rows(balances, classes):
    # Un groups ke ledgers jinki classification classes me hai: [(group, [(ledger, dr_minus_cr)])]
    groups = ChartOfAccountsGroup.query.filter(ChartOfAccountsGroup.classification.in_(classes)).order_by(ChartOfAccountsGroup.id).all()
    out = []
    for group in groups:
        rows = []
        for ledger in Ledger.query.filter_by(group_id=group.id).order_by(Ledger.name).all():
            value = balances.get(ledger.id, 0)
            if value != 0:
                rows.append((ledger, value))
        out.append((group, rows))
    return out


def trial_balance(as_on):
    """as_on tak har ledger ka closing. Party groups ek line me (ledger ginti ke saath). Return (groups, total_dr, total_cr); paise me."""
    balances = movements(None, as_on)
    groups, total_dr, total_cr = [], 0, 0
    for group, rows in _ledger_rows(balances, ("ASSET", "LIABILITY", "EQUITY", "INCOME", "EXPENSE")):
        if not rows:
            continue
        dr = sum(v for _l, v in rows if v > 0)
        cr = -sum(v for _l, v in rows if v < 0)
        # Party group me ledger bahut ho sakte hain — sirf group ka jod dikhate hain
        is_party = group.name in PARTY_GROUPS
        net = dr - cr
        if is_party:
            groups.append({"group": group, "party": True, "count": len(rows), "ledgers": [], "dr": max(net, 0), "cr": max(-net, 0)})
            total_dr += dr
            total_cr += cr
            continue
        groups.append({"group": group, "party": False, "count": len(rows), "ledgers": [(l, max(v, 0), max(-v, 0)) for l, v in rows], "dr": dr, "cr": cr})
        total_dr += dr
        total_cr += cr
    return groups, total_dr, total_cr


def profit_loss(date_from, date_to):
    """Period ka P&L. Income = Cr - Dr, Expense = Dr - Cr. Return dict (paise me): income lines, direct / indirect expense lines, gross, net."""
    balances = movements(date_from, date_to)
    income, direct, indirect = [], [], []
    for group, rows in _ledger_rows(balances, ("INCOME", "EXPENSE")):
        for ledger, value in rows:
            if group.classification == "INCOME":
                income.append((ledger, -value))
            elif group.name in DIRECT_GROUPS:
                direct.append((ledger, value))
            else:
                indirect.append((ledger, value))
    income_total = sum(v for _l, v in income)
    direct_total = sum(v for _l, v in direct)
    indirect_total = sum(v for _l, v in indirect)
    gross = income_total - direct_total
    return {"income": income, "direct": direct, "indirect": indirect, "income_total": income_total, "direct_total": direct_total,
            "indirect_total": indirect_total, "gross": gross, "net": gross - indirect_total}


def books_stock_value(as_on):
    # Stock-in-hand ledger ka voucher balance (Dr plus)
    ledger = Ledger.query.filter_by(system_key="stock_in_hand").first()
    return movements(None, as_on).get(ledger.id, 0) if ledger else 0


def inventory_stock_value():
    # Inventory records ke hisaab se maal ki value (raw material + finished goods), sirf tulna ke liye — WIP aur transit isme nahi
    rm = db.session.query(func.sum(StockMovement.value)).scalar() or 0
    fg = db.session.query(func.sum(FGMovement.value)).scalar() or 0
    return _cents(rm) + _cents(fg)


def balance_sheet(as_on):
    """as_on tak. Left = Liabilities + Equity + cumulative Profit; right = Assets. Paise me. Difference hamesha 0 hona chahiye."""
    balances = movements(None, as_on)
    liabilities, assets = [], []
    for group, rows in _ledger_rows(balances, ("EQUITY", "LIABILITY", "ASSET")):
        if not rows:
            continue
        net = sum(v for _l, v in rows)             # Dr - Cr
        if group.classification == "ASSET":
            assets.append({"group": group, "amount": net, "count": len(rows), "ledgers": [] if group.name in PARTY_GROUPS else [(l, v) for l, v in rows]})
        else:
            liabilities.append({"group": group, "amount": -net, "count": len(rows), "ledgers": [] if group.name in PARTY_GROUPS else [(l, -v) for l, v in rows]})
    # Ab tak ka poora profit (sab saal) — warna Assets = Liabilities nahi milta
    pl = profit_loss(None, as_on)
    liab_total = sum(r["amount"] for r in liabilities) + pl["net"]
    asset_total = sum(r["amount"] for r in assets)
    return {"liabilities": liabilities, "assets": assets, "profit": pl["net"], "liab_total": liab_total, "asset_total": asset_total,
            "difference": asset_total - liab_total, "stock_books": books_stock_value(as_on), "stock_inventory": inventory_stock_value()}


def day_book(date_from, date_to, limit=500):
    query = Voucher.query.filter(Voucher.voucher_date >= date_from, Voucher.voucher_date <= date_to)
    total = query.count()
    return query.order_by(Voucher.voucher_date, Voucher.id).limit(limit).all(), total


def money(cents):
    return "{:,.2f}".format(cents / 100)
