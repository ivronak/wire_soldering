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
        row = {"lot": lot, "unit": lot_unit(lot), "waiting": 0, "available": 0, "rejected": 0, "value": 0, "where": []}
        has_qc = lot.grn_line.final_qc is not None if lot.grn_line else False
        for warehouse_id, qty, value in sums.get(lot.id, []):
            if abs(qty) < 0.00005:
                continue
            warehouse = warehouses.get(warehouse_id)
            row["where"].append(warehouse.name if warehouse else "?")
            row["value"] += value
            if warehouse is not None and warehouse.warehouse_type == "QC_HOLD":
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
        item = summary.setdefault(key, {"material": row["lot"].raw_material, "unit": row["unit"], "waiting": 0, "available": 0, "rejected": 0, "value": 0})
        for name in ("waiting", "available", "rejected", "value"):
            item[name] += row[name]
    summary_rows = sorted(summary.values(), key=lambda item: item["material"].name if item["material"] else "")

    return render_template("stock.html", active_nav="stock", lot_rows=lot_rows, summary_rows=summary_rows)


@inventory_bp.route("/inventory/stock/<int:lot_id>")
def stock_lot(lot_id):
    lot = db.session.get(StockLot, lot_id)
    if lot is None:
        abort(404)
    movements = StockMovement.query.filter_by(lot_id=lot.id).order_by(StockMovement.id).all()
    running = 0
    rows = []
    for movement in movements:
        running = round(running + movement.qty, 4)
        rows.append({"m": movement, "label": MOVEMENT_LABELS.get(movement.movement_type, movement.movement_type), "running": running})
    return render_template("stock_lot.html", active_nav="stock", lot=lot, unit=lot_unit(lot), rows=rows)
