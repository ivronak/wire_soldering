# Sales S3 — Dispatch ka stock hisaab: kis line ka kitna dispatch hua, kitna maal ready hai (us order ka + free / Own stock), batch allocation.
# Stock ki rows FG ledger (fg_movements, type DISPATCH) me sirf yahin ke functions likhte hain; routes nahi.
#
# Rules (user ke saath tay, 18 Nov):
#   * Har batch kisi production order ka hota hai. Wo order kisi Ordered quotation line se juda ho to us line ke "pending" tak ka maal us line ke liye RESERVED hai
#     (usi party ka). Bacha hua maal FREE (Own stock) hai — kisi bhi line ko extra diya ja sakta hai.
#   * Dispatch par pehle line ke apne order ka maal (purana batch pehle), phir free stock (purana batch pehle).
#   * Cancel = ulti rows; kabhi UPDATE / DELETE nahi.
from sqlalchemy import func

from app.extensions import db
from app.inventory.money import q2, q4, value_for_out
from app.models import DeliveryChallan, DeliveryChallanLine, FGBatch, FGMovement, ProductionOutput, Quotation, QuotationLine


class DispatchError(Exception):
    pass


def dispatched_qty(line):
    # Is quotation line ka ab tak kitna maal gaya (cancel hue challan nahi ginte)
    total = (db.session.query(func.coalesce(func.sum(DeliveryChallanLine.qty), 0))
             .join(DeliveryChallan, DeliveryChallan.id == DeliveryChallanLine.challan_id)
             .filter(DeliveryChallanLine.quotation_line_id == line.id, DeliveryChallan.status == "Dispatched", DeliveryChallan.is_deleted == False)
             .scalar())
    return q4(total)


def pending_qty(line):
    return max(q4(line.qty - dispatched_qty(line)), 0.0)


def _owner_line(batch):
    # Is batch ka production order kisi Ordered quotation ki line se juda ho to wahi line (us party ka maal)
    return (QuotationLine.query.join(Quotation, Quotation.id == QuotationLine.quotation_id)
            .filter(QuotationLine.production_order_id == batch.production_order_id, Quotation.is_deleted == False, Quotation.status == "Ordered")
            .first())


def batch_view(product_id):
    """Is product ke FG batch jinme maal bacha hai (purana pehle): [{batch, balance, reserved, free, owner}]. reserved = owner line ke pending tak."""
    batches = (FGBatch.query.join(ProductionOutput, ProductionOutput.id == FGBatch.output_id)
               .filter(FGBatch.kind == "FG", FGBatch.product_id == product_id, ProductionOutput.status == "Posted", ProductionOutput.is_deleted == False)
               .order_by(FGBatch.mfg_date, FGBatch.id).all())
    rows = []
    for batch in batches:
        balance, _value = batch.balance
        if balance <= 0.00005:
            continue
        owner = _owner_line(batch)
        reserved = min(pending_qty(owner), balance) if owner is not None else 0.0
        rows.append({"batch": batch, "balance": balance, "reserved": q4(reserved), "free": q4(balance - reserved), "owner": owner})
    return rows


def availability(line, view=None):
    """Is line ko abhi kitna maal diya ja sakta hai: own (us order ka reserved) + free (Own stock). {own, free, available}"""
    view = batch_view(line.product_id) if view is None else view
    own = sum(r["reserved"] for r in view if r["owner"] is not None and r["owner"].id == line.id)
    free = sum(r["free"] for r in view)
    return {"own": q4(own), "free": q4(free), "available": q4(own + free)}


def allocate(line, qty, view=None):
    """qty maal kin batch se jayega: [(batch, qty, from_own)]. Pehle line ke apne order ke batch, phir free stock. Kam ho to DispatchError."""
    view = batch_view(line.product_id) if view is None else view
    need = q4(qty)
    picks = []
    for row in view:
        if need <= 0.00005:
            break
        if row["owner"] is not None and row["owner"].id == line.id and row["reserved"] > 0:
            take = min(need, row["reserved"])
            picks.append((row["batch"], q4(take), True))
            need = q4(need - take)
    for row in view:
        if need <= 0.00005:
            break
        if row["free"] > 0.00005:
            take = min(need, row["free"])
            picks.append((row["batch"], q4(take), False))
            need = q4(need - take)
    if need > 0.00005:
        raise DispatchError(f"Not enough finished goods in stock: {need:g} more is needed.")
    return picks


def batch_warehouse(batch):
    # Batch jis FG warehouse me aaya (pehli movement ka warehouse — Finished goods page bhi yahi dikhata hai)
    first = next((m.warehouse for m in batch.movements if m.warehouse is not None), None)
    if first is None:
        raise DispatchError(f"Batch {batch.batch_no} has no warehouse.")
    return first


def next_challan_no(challan_date):
    # DC-<saal>-<agla number>: sabse bada number dekhte hain (count nahi), taaki gap hone par bhi number repeat na ho
    prefix = f"DC-{challan_date.year}-"
    last = 0
    for (number,) in db.session.query(DeliveryChallan.challan_no).filter(DeliveryChallan.challan_no.like(prefix + "%")).all():
        try:
            last = max(last, int(number.split("-")[-1]))
        except ValueError:
            pass
    return f"{prefix}{last + 1:03d}"


def create_challan(quotation, challan_date, wanted, transporter=None, vehicle_no=None, notes=None):
    """wanted = {quotation_line: qty}. Challan + lines + FG stock ki DISPATCH rows. Kuch kam ho to DispatchError (caller rollback karta hai)."""
    challan = DeliveryChallan(challan_no=next_challan_no(challan_date), quotation_id=quotation.id, challan_date=challan_date,
                              transporter=transporter, vehicle_no=vehicle_no, notes=notes, status="Dispatched")
    db.session.add(challan)
    db.session.flush()
    for line, qty in wanted.items():
        view = batch_view(line.product_id)                 # har line se pehle taaza (pichhli line ne stock nikala ho sakta hai)
        for batch, take, from_own in allocate(line, qty, view):
            balance, value = batch.balance
            cost_value = value_for_out(balance, value, take)
            warehouse = batch_warehouse(batch)
            db.session.add(FGMovement(batch_id=batch.id, warehouse_id=warehouse.id, movement_date=challan_date, movement_type="DISPATCH", qty=-take,
                                      value=-cost_value, ref_type="DC", ref_id=challan.id, ref_no=challan.challan_no,
                                      note=f"Dispatched to {quotation.customer.name}"[:255]))
            db.session.add(DeliveryChallanLine(challan_id=challan.id, quotation_line_id=line.id, batch_id=batch.id, qty=take,
                                               unit_cost=round(cost_value / take, 4) if take else 0, from_own_order=from_own))
            db.session.flush()
    return challan


def cancel_challan(challan, reason):
    """Challan cancel: har DISPATCH row ki ulti row (maal wapas FG stock me)."""
    for move in FGMovement.query.filter_by(ref_type="DC", ref_id=challan.id, movement_type="DISPATCH").filter(FGMovement.reverses_movement_id.is_(None)).all():
        if FGMovement.query.filter_by(reverses_movement_id=move.id).first() is not None:
            continue
        db.session.add(FGMovement(batch_id=move.batch_id, warehouse_id=move.warehouse_id, movement_date=move.movement_date, movement_type="DISPATCH",
                                  qty=q4(-move.qty), value=q2(-move.value), ref_type="DC", ref_id=challan.id, ref_no=challan.challan_no,
                                  reverses_movement_id=move.id, note="Reversal: challan cancelled"))
    challan.status = "Cancelled"
    challan.cancel_reason = reason
    db.session.flush()


def dispatch_state(quotation):
    # Ordered quotation ka dispatch haal: "Not dispatched" / "Partly dispatched" / "Dispatched" (sab lines poori ya zyada gayi)
    if quotation.status != "Ordered":
        return None
    done = [dispatched_qty(line) for line in quotation.lines]
    if not any(q > 0.00005 for q in done):
        return "Not dispatched"
    if all(d + 0.00005 >= line.qty for d, line in zip(done, quotation.lines)):
        return "Dispatched"
    return "Partly dispatched"
