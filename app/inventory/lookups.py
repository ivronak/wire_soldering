# Stock transfer / adjustment ke forms ke liye: kis warehouse me kaun se lot ka kitna maal hai.
# Sirf padhta hai (ledger rows ka SUM), kuch likhta nahi.
from sqlalchemy import func

from app.extensions import db
from app.models import StockLot, StockMovement


def lot_label(lot):
    material = lot.raw_material.name if lot.raw_material else "Material"
    batch = (" · batch " + lot.vendor_batch_no) if lot.vendor_batch_no else ""
    return f"{material} · {lot.lot_code}{batch}"


def lot_unit_code(lot):
    po_line = lot.grn_line.po_line if lot.grn_line else None
    return po_line.unit.code if po_line and po_line.unit else ""


def warehouse_lot_options(include_empty=False):
    # {warehouse_id: [{lot_id, label, unit, qty}]}. include_empty=True: wo lots bhi jinka is warehouse me kabhi koi movement hua
    # (qty 0 ho tab bhi) — adjustment (found stock) me kaam aata hai.
    rows = db.session.query(StockMovement.warehouse_id, StockMovement.lot_id, func.sum(StockMovement.qty)).group_by(
        StockMovement.warehouse_id, StockMovement.lot_id).all()
    lots = {lot.id: lot for lot in StockLot.query.all()}
    options = {}
    for warehouse_id, lot_id, qty in rows:
        qty = round(qty or 0, 4)
        if qty <= 0.00005 and not include_empty:
            continue
        lot = lots.get(lot_id)
        if lot is None:
            continue
        options.setdefault(warehouse_id, []).append({"lot_id": lot.id, "label": lot_label(lot), "unit": lot_unit_code(lot), "qty": qty})
    for warehouse_id in options:
        options[warehouse_id].sort(key=lambda item: item["lot_id"])
    return options
