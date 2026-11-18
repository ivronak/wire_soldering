# Sales S7 — Sales Return / Credit Note: Posted invoice ka maal customer ne wapas bheja.
# Judta hai: sales_invoices (kya bill hua), delivery_challan_lines (kaunse batch se gaya, cost kya thi), fg_movements (stock), customers.ledger.
#
# Rules (memory.md S7 decision):
#   * Sirf Posted invoice ke against; qty invoice ki line ke "abhi tak wapas nahi aaye" maal se zyada nahi.
#   * Credit = qty x (rate, discount ke baad) + us line ka GST. Invoice ke charges (shipping...) wapas nahi hote (abhi).
#   * Achha maal (good) usi batch me wapas FG stock me — jis batch se gaya tha (type SALES_RETURN, cost challan wali). Kharab (damaged) stock me nahi aata.
#   * Ledger sign rule (project): Cr = plus. Credit note se customer ledger me Cr (lena kam); cancel = ulta.
#   * Cancel tabhi jab wapas aaya maal stock me abhi hai (dobara dispatch na ho gaya ho). Stock ki rows kabhi delete nahi — ulti row.
from datetime import datetime

from app.dispatch.stock import batch_warehouse
from app.extensions import db
from app.inventory.money import q2, q4
from app.models import FGMovement, SalesReturn, SalesReturnLine

TOLERANCE = 0.00005


class ReturnError(Exception):
    pass


def next_return_no(return_date):
    # CN-<saal>-<agla number>: sabse bada number dekhte hain (count nahi), taaki gap hone par bhi number repeat na ho
    prefix = f"CN-{return_date.year}-"
    last = 0
    for (number,) in db.session.query(SalesReturn.return_no).filter(SalesReturn.return_no.like(prefix + "%")).all():
        try:
            last = max(last, int(number.split("-")[-1]))
        except ValueError:
            pass
    return f"{prefix}{last + 1:03d}"


def returned_qty(invoice_line):
    # Is invoice line ka ab tak kitna maal wapas aaya (Cancelled credit note nahi ginte)
    total = 0.0
    for row in invoice_line.return_lines:
        if row.sales_return.status == "Posted" and not row.sales_return.is_deleted:
            total += row.qty
    return q4(total)


def returnable_qty(invoice_line):
    return max(q4(invoice_line.qty - returned_qty(invoice_line)), 0.0)


def _challan_rows(invoice_line):
    # Is invoice line ka maal jin challan rows (batch) se gaya (bill ke challans, purana pehle)
    rows = []
    for challan in sorted(invoice_line.invoice.challans, key=lambda c: c.id):
        if challan.status != "Dispatched":
            continue
        for cl in challan.lines:
            if cl.quotation_line_id == invoice_line.quotation_line_id:
                rows.append(cl)
    return rows


def _challan_row_left(challan_line):
    done = sum(r.qty for r in challan_line.return_lines if r.sales_return.status == "Posted" and not r.sales_return.is_deleted)
    return max(q4(challan_line.qty - done), 0.0)


def returnable_invoices(customer_id=None):
    # Posted invoices jinme kuch wapas aa sakta hai (return form ki list)
    from app.models import Quotation, SalesInvoice
    query = (SalesInvoice.query.join(Quotation, Quotation.id == SalesInvoice.quotation_id)
             .filter(SalesInvoice.status == "Posted", SalesInvoice.is_deleted == False))
    if customer_id:
        query = query.filter(Quotation.customer_id == customer_id)
    return [inv for inv in query.order_by(SalesInvoice.id.desc()).all() if any(returnable_qty(line) > TOLERANCE for line in inv.lines)]


def create_return(invoice, return_date, reason, wanted):
    """wanted = {invoice_line_id: (qty, damaged_qty)}. Credit note + rows + stock + ledger. Galti par ReturnError (caller rollback karta hai)."""
    if invoice.status != "Posted" or invoice.is_deleted:
        raise ReturnError("A sales return can be made only against a posted invoice.")
    if return_date < invoice.invoice_date:
        raise ReturnError("The return date cannot be before the invoice date.")
    reason = (reason or "").strip()
    if len(reason) < 3:
        raise ReturnError("Write the reason for the return.")
    picked = []
    for line in invoice.lines:
        qty, damaged = wanted.get(line.id, (0.0, 0.0))
        qty, damaged = q4(qty), q4(damaged)
        if qty <= TOLERANCE:
            continue
        name = line.product.name
        if qty < 0 or damaged < 0:
            raise ReturnError(f"{name}: quantities cannot be negative.")
        if qty > returnable_qty(line) + TOLERANCE:
            raise ReturnError(f"{name}: only {returnable_qty(line):g} is left to return on this invoice.")
        if damaged > qty + TOLERANCE:
            raise ReturnError(f"{name}: damaged quantity cannot be more than the returned quantity.")
        picked.append((line, qty, damaged))
    if not picked:
        raise ReturnError("Enter the quantity returned for at least one item.")

    ret = SalesReturn(return_no=next_return_no(return_date), invoice_id=invoice.id, return_date=return_date, reason=reason, status="Posted")
    db.session.add(ret)
    db.session.flush()
    for line, qty, damaged in picked:
        good_left = q4(qty - damaged)                      # kitna achha maal stock me jaana hai (batch me baantna hai)
        need = qty
        for cl in _challan_rows(line):
            if need <= TOLERANCE:
                break
            take = min(need, _challan_row_left(cl))
            if take <= TOLERANCE:
                continue
            restock = min(take, good_left)
            good_left = q4(good_left - restock)
            need = q4(need - take)
            db.session.add(SalesReturnLine(return_id=ret.id, invoice_line_id=line.id, challan_line_id=cl.id, batch_id=cl.batch_id, qty=q4(take), good_qty=q4(restock)))
            if restock > TOLERANCE:
                db.session.add(FGMovement(batch_id=cl.batch_id, warehouse_id=batch_warehouse(cl.batch).id, movement_date=return_date, movement_type="SALES_RETURN",
                                          qty=q4(restock), value=q2(restock * (cl.unit_cost or 0)), ref_type="SR", ref_id=ret.id, ref_no=ret.return_no,
                                          note=f"Returned by {invoice.quotation.customer.name}"[:255]))
        if need > TOLERANCE:
            raise ReturnError(f"{line.product.name}: the dispatch records do not cover this quantity.")
    db.session.flush()
    db.session.refresh(ret)

    result = ret.summary
    ret.subtotal = round(result["items_total"] - result["discount_total"], 2)
    ret.tax_total = result["tax_total"]
    ret.total_amount = result["grand_total"]
    ledger = invoice.quotation.customer.ledger
    ledger.current_balance = round(ledger.current_balance + ret.total_amount, 2)      # Cr: lena kam
    db.session.flush()
    return ret


def cancel_return(ret, reason):
    """Credit note cancel: ledger wapas (lena phir badha), stock ki ulti rows. Maal dobara bhej diya ho to cancel nahi hota."""
    if ret.status == "Cancelled":
        raise ReturnError("This credit note is already cancelled.")
    moves = [m for m in FGMovement.query.filter_by(ref_type="SR", ref_id=ret.id, movement_type="SALES_RETURN").all()
             if m.reverses_movement_id is None and FGMovement.query.filter_by(reverses_movement_id=m.id).first() is None]
    for move in moves:
        balance, _value = move.batch.balance
        if balance + TOLERANCE < move.qty:
            raise ReturnError(f"The returned goods of batch {move.batch.batch_no} are no longer all in stock (they were dispatched again), so this credit note cannot be cancelled.")
    for move in moves:
        db.session.add(FGMovement(batch_id=move.batch_id, warehouse_id=move.warehouse_id, movement_date=move.movement_date, movement_type="SALES_RETURN",
                                  qty=q4(-move.qty), value=q2(-move.value), ref_type="SR", ref_id=ret.id, ref_no=ret.return_no,
                                  reverses_movement_id=move.id, note="Reversal: credit note cancelled"))
    ledger = ret.invoice.quotation.customer.ledger
    ledger.current_balance = round(ledger.current_balance - ret.total_amount, 2)
    ret.status = "Cancelled"
    ret.cancel_reason = reason
    ret.cancelled_at = datetime.utcnow()
    db.session.flush()
