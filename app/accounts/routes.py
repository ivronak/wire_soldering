# Accounts module (A1): abhi sirf "Chart of accounts" — groups ka tree + har group ke ledgers, sirf dekhne ke liye.
# Customer / Vendor ke ledger bahut ho sakte hain, isliye unke liye sirf ginti dikhate hain (list Customers / Vendors me hai).
# Voucher banana, edit karna aage ke steps (A3+) me. Table: chart_of_accounts_groups, ledgers (models.py).
from flask import Blueprint, render_template, request
from sqlalchemy import func

from app.extensions import db
from app.models import ChartOfAccountsGroup, Ledger

accounts_bp = Blueprint("accounts", __name__, template_folder="templates")

# In groups ke ledger party ke hain (Customer / Vendor banate waqt apne aap bante hain)
PARTY_GROUPS = ("Sundry Debtors", "Sundry Creditors")


def _tree():
    # Groups ko parent -> child tree me; har group ke saath uske ledgers (party group me sirf count)
    groups = ChartOfAccountsGroup.query.order_by(ChartOfAccountsGroup.id).all()
    counts = dict(db.session.query(Ledger.group_id, func.count(Ledger.id)).group_by(Ledger.group_id).all())
    by_parent = {}
    for group in groups:
        by_parent.setdefault(group.parent_id, []).append(group)

    def build(parent_id, depth):
        rows = []
        for group in by_parent.get(parent_id, []):
            is_party = group.name in PARTY_GROUPS
            ledgers = [] if is_party else Ledger.query.filter_by(group_id=group.id).order_by(Ledger.name).all()
            rows.append({"group": group, "depth": depth, "is_party": is_party, "ledger_count": counts.get(group.id, 0), "ledgers": ledgers})
            rows.extend(build(group.id, depth + 1))
        return rows

    return build(None, 0)


@accounts_bp.route("/accounts/chart")
def chart_page():
    q = (request.args.get("q") or "").strip().lower()
    rows = _tree()
    if q:
        # Search: group ka naam ya uske kisi ledger ka naam match kare to wo group dikhao
        rows = [r for r in rows if q in r["group"].name.lower() or any(q in l.name.lower() for l in r["ledgers"])]
    return render_template("chart_of_accounts.html", rows=rows, q=q)
