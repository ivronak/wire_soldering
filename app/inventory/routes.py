# Stock pages (sirf padhne ke liye): Stock list (lot-wise + material-wise) aur ek lot ka poora ledger.
# Stock badalne ke rules app/inventory/posting.py me hain; yahan kuch save nahi hota.
from flask import render_template, Blueprint, abort
from sqlalchemy import func

from app.extensions import db
from app.models import StockLot, StockMovement

inventory_bp = Blueprint("inventory", __name__, template_folder="templates")

MOVEMENT_LABELS = {
    "GRN_RECEIPT": "Received (GRN)",
    "QC_OUT": "Passed QC: left QC Hold",
    "QC_IN": "Passed QC: into store",
    "PURCHASE_RETURN": "Returned to vendor",
    "ISSUE_OUT": "Issued to production: left store",
    "ISSUE_IN": "Issued to production: into WIP",
}


def lot_unit(lot):
    po_line = lot.grn_line.po_line if lot.grn_line else None
    return po_line.unit.code if po_line and po_line.unit else ""


@inventory_bp.route("/inventory/stock")
def stock_list():
    # Har lot ka balance warehouse-wise (rows ka SUM), phir 3 dabbe:
    #   Waiting for QC = QC Hold me, jis lot ka final QC abhi nahi hua
    #   Available      = QC pass ho ke store (RM) warehouse me
    #   Rejected       = QC Hold me, QC ke baad bacha hua (rejected, jab tak Purchase Return se na jaye)
    sums = {}
    query = db.session.query(StockMovement.lot_id, StockMovement.warehouse_id, func.sum(StockMovement.qty), func.sum(StockMovement.value)).group_by(
        StockMovement.lot_id, StockMovement.warehouse_id)
    for lot_id, warehouse_id, qty, value in query.all():
        sums.setdefault(lot_id, []).append((warehouse_id, round(qty or 0, 4), round(value or 0, 2)))

    from app.models import Warehouse
    warehouses = {w.id: w for w in Warehouse.query.all()}

    lot_rows = []
    for lot in StockLot.query.order_by(StockLot.id.desc()).all():
        row = {"lot": lot, "unit": lot_unit(lot), "waiting": 0, "available": 0, "rejected": 0, "wip": 0, "value": 0, "where": []}
        has_qc = lot.grn_line.final_qc is not None if lot.grn_line else False
        for warehouse_id, qty, value in sums.get(lot.id, []):
            if abs(qty) < 0.00005:
                continue
            warehouse = warehouses.get(warehouse_id)
            row["where"].append(warehouse.name if warehouse else "?")
            row["value"] += value
            if warehouse is not None and warehouse.warehouse_type == "WIP":
                row["wip"] += qty
            elif warehouse is not None and warehouse.warehouse_type == "QC_HOLD":
                if has_qc:
                    row["rejected"] += qty
                else:
                    row["waiting"] += qty
            else:
                row["available"] += qty
        row["value"] = round(row["value"], 2)
        lot_rows.append(row)

    # Material-wise jod (material + unit ek saath: alag units ka qty jodna galat hota)
    summary = {}
    for row in lot_rows:
        key = (row["lot"].raw_material_id, row["unit"])
        item = summary.setdefault(key, {"material": row["lot"].raw_material, "unit": row["unit"], "waiting": 0, "available": 0, "rejected": 0, "wip": 0, "value": 0})
        for name in ("waiting", "available", "rejected", "wip", "value"):
            item[name] += row[name]
    summary_rows = sorted(summary.values(), key=lambda item: item["material"].name if item["material"] else "")

    return render_template("stock.html", active_nav="stock", lot_rows=lot_rows, summary_rows=summary_rows)


# Lot history ki ek "event" = ek kaam (jaise QC pass). Ek kaam ki do rows (ek godown se minus, doosre me plus) ek line me dikhti hain.
EVENT_TITLES = {
    "GRN": "Goods received",
    "QC": "Quality check passed",
    "ISSUE": "Issued to production",
    "RETURN": "Returned to vendor",
}


def build_events(movements, unit):
    groups = {}
    order = []
    for movement in movements:
        key = (movement.ref_type, movement.ref_id, movement.line_key, movement.reverses_movement_id is not None)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(movement)

    events = []
    for key in order:
        rows = groups[key]
        ref_type, _ref_id, _line_key, cancelled = key
        first = rows[0]
        leaving = [r for r in rows if r.qty < 0]
        arriving = [r for r in rows if r.qty > 0]
        qty = abs(first.qty)
        title = EVENT_TITLES.get(ref_type, ref_type)
        if cancelled:
            title = "Cancelled: " + title.lower()
        if first.note and first.note.startswith("Correction"):
            title = "Correction"
            cancelled = False
        qty_text = ("%g" % qty) + " " + unit

        def name(row):
            return row.warehouse.name if row.warehouse else "?"

        if leaving and arriving:
            kind = "move"
            sentence = "%s moved from %s to %s." % (qty_text, name(leaving[0]), name(arriving[0]))
            value = abs(arriving[0].value)
        elif arriving:
            kind = "in"
            verb = "came back into" if cancelled else "came into"
            sentence = "%s %s %s." % (qty_text, verb, name(arriving[0]))
            value = abs(arriving[0].value)
        else:
            kind = "out"
            tail = " back to the vendor" if ref_type == "RETURN" else ""
            sentence = "%s went out of %s%s." % (qty_text, name(leaving[0]), tail)
            value = abs(leaving[0].value)
        events.append({
            "date": first.movement_date, "created_at": first.created_at, "title": title, "sentence": sentence,
            "kind": kind, "qty": qty, "value": value, "ref_no": first.ref_no, "cancelled": cancelled,
        })
    return events


@inventory_bp.route("/inventory/stock/<int:lot_id>")
def stock_lot(lot_id):
    lot = db.session.get(StockLot, lot_id)
    if lot is None:
        abort(404)
    unit = lot_unit(lot)
    movements = StockMovement.query.filter_by(lot_id=lot.id).order_by(StockMovement.id).all()

    # "Abhi kahan kitna hai": har godown ka balance (rows ka SUM)
    from app.models import Warehouse
    has_qc = lot.grn_line.final_qc is not None if lot.grn_line else False
    totals = {}
    for movement in movements:
        item = totals.setdefault(movement.warehouse_id, [0, 0])
        item[0] += movement.qty
        item[1] += movement.value
    where_now = []
    for warehouse_id, (qty, value) in totals.items():
        if abs(qty) < 0.00005:
            continue
        warehouse = db.session.get(Warehouse, warehouse_id)
        wtype = warehouse.warehouse_type if warehouse else ""
        if wtype == "QC_HOLD":
            label = "Rejected, waiting to go back" if has_qc else "Waiting for QC"
            tone = "bad" if has_qc else "wait"
        elif wtype == "WIP":
            label, tone = "In production", "wip"
        else:
            label, tone = "Available to use", "good"
        where_now.append({"warehouse": warehouse.name if warehouse else "?", "label": label, "tone": tone,
                          "qty": round(qty, 4), "value": round(value, 2)})
    where_now.sort(key=lambda w: {"good": 0, "wip": 1, "wait": 2, "bad": 3}[w["tone"]])

    received = sum(m.qty for m in movements if m.movement_type == "GRN_RECEIPT" and m.reverses_movement_id is None)
    return render_template("stock_lot.html", active_nav="stock", lot=lot, unit=unit,
                           events=build_events(movements, unit), where_now=where_now, received=received)
