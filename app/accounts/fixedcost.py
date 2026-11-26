# Accounts: production ke fixed cost ka voucher. Costing (app/costing/fixed.py) har output par fixed_cost_total nikalta hai; yahan uska accounts me asar.
# Voucher: Dr Stock-in-hand (maal ki cost badhi), Cr Fixed Cost Payable (rent / salary / bijli jo abhi chukana baaki hai). Type = Journal.
# Kyun "delta" voucher: fixed cost baad me badal sakta hai (din me doosra output aaya, mahina Final hua, output cancel hua). Isliye har baar dekhte hain
# ki output par ab kitna fixed cost hona chahiye aur accounts me kitna ja chuka, sirf farak ka naya voucher (plus ho to Dr Stock, minus ho to ulta). Purana kabhi edit nahi.
# COGS ko haath nahi: bikri ke waqt COGS pehle se batch cost (material + fixed) se banta hai.
from datetime import date

from app.accounts.posting import post_voucher, system_ledger
from app.extensions import db
from app.models import ProductionOutput, Voucher, VoucherEntry

SRC_FIXED_COST = "production_fixed_cost"


def posted_so_far(output_id):
    # Is output ke fixed-cost vouchers ka jod (Fixed Cost Payable par Cr = plus). Reversal voucher apne aap ghat deta hai.
    payable = system_ledger("fixed_cost_payable")
    rows = (db.session.query(VoucherEntry.side, VoucherEntry.amount).join(Voucher, Voucher.id == VoucherEntry.voucher_id)
            .filter(Voucher.source_type == SRC_FIXED_COST, Voucher.source_id == output_id, VoucherEntry.ledger_id == payable.id).all())
    return round(sum((amount if side == "Cr" else -amount) for side, amount in rows), 2)


def sync_output(output, created_by_id=None):
    """Output par ab jitna fixed cost hona chahiye wahi accounts me rakho. Voucher banaya to lautata hai, farak nahi to None."""
    if output.id is None:
        db.session.flush()
    if created_by_id is None:
        from app.auth import service as auth_service          # 'kisne kiya': logged-in user (CLI / backfill me koi nahi = None)
        try:
            created_by_id = auth_service.actor_id()
        except RuntimeError:
            created_by_id = None
    wanted = round(output.fixed_cost_total or 0, 2) if (output.status == "Posted" and not output.is_deleted) else 0.0
    done = posted_so_far(output.id)
    delta = round(wanted - done, 2)
    if abs(delta) < 0.005:
        return None
    first = abs(done) < 0.005
    day = output.output_date if first else date.today()          # pehli entry output ki tareekh par; baad ka sudhaar aaj ki tareekh par (purane mahine ke aankde na hilein)
    side_stock, side_payable = ("Dr", "Cr") if delta > 0 else ("Cr", "Dr")
    lines = [(system_ledger("stock_in_hand"), side_stock, abs(delta)), (system_ledger("fixed_cost_payable"), side_payable, abs(delta))]
    note = "Fixed cost on %s" % output.output_no if first else "Fixed cost adjusted on %s (%s)" % (output.output_no, output.status)
    return post_voucher("Journal", day, lines, narration=note, source_type=SRC_FIXED_COST, source_id=output.id, created_by_id=created_by_id)


def sync_day(day, created_by_id=None):
    # Us din ke saare outputs (cancel hue bhi) — din ka kharcha dobara bantne par sabka fixed cost badal sakta hai
    outputs = ProductionOutput.query.filter(ProductionOutput.is_deleted == False, ProductionOutput.output_date == day).all()      # noqa: E712
    return [v for v in (sync_output(o, created_by_id) for o in outputs) if v is not None]


def backfill(created_by_id=None):
    # Purane outputs (accounts se pehle ke) jinka fixed cost hai par voucher nahi: ek baar chalao. Dobara chalane par kuch nahi banta.
    outputs = ProductionOutput.query.filter(ProductionOutput.is_deleted == False).all()      # noqa: E712
    return [v for v in (sync_output(o, created_by_id) for o in outputs) if v is not None]
