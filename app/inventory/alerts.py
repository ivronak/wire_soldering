# Reorder / min / max alerts: Raw Material master me jo level likhe hain unse store (RM warehouse) ke maal ko milate hain.
# Sirf padhta hai, kuch save nahi karta. Stock page ka "Needs attention" aur sidebar ka lal ginti isi se aata hai.
from sqlalchemy import func

from app.extensions import db
from app.models import PurchaseOrder, RawMaterial, StockMovement, Warehouse


def store_stock_by_material():
    # {raw_material_id: qty} — sirf RM (store) warehouses me jo maal use ho sakta hai. QC Hold / WIP / Scrap / transit nahi.
    rows = db.session.query(StockMovement.raw_material_id, func.sum(StockMovement.qty)).join(
        Warehouse, Warehouse.id == StockMovement.warehouse_id).filter(Warehouse.warehouse_type == "RM").group_by(StockMovement.raw_material_id).all()
    return {material_id: round(qty or 0, 4) for material_id, qty in rows}


def on_order_by_material():
    # {raw_material_id: qty} — confirm hue (Open / Partial) PO ki lines me abhi aana baaki maal
    totals = {}
    for po in PurchaseOrder.query.filter(PurchaseOrder.is_deleted == False, PurchaseOrder.status.in_(["Open", "Partial"])).all():
        for line in po.lines:
            if line.remaining_qty > 0:
                totals[line.raw_material_id] = round(totals.get(line.raw_material_id, 0) + line.remaining_qty, 4)
    return totals


ORDER = {"out": 0, "critical": 1, "low": 2, "over": 3}
LABELS = {"out": "Out of stock", "critical": "Below minimum", "low": "Reorder now", "over": "Above maximum"}


def stock_alerts():
    # Wapas: {"rows": [...alert...], "unset": kitne materials ke level likhe hi nahi}
    available = store_stock_by_material()
    on_order = on_order_by_material()
    rows = []
    unset = 0
    for material in RawMaterial.query.filter(RawMaterial.is_deleted == False, RawMaterial.is_active == True).order_by(RawMaterial.name).all():
        reorder, minimum, maximum = material.reorder_level, material.min_stock, material.max_stock
        if not reorder and not minimum and not maximum:
            unset += 1
            continue
        have = available.get(material.id, 0)
        coming = on_order.get(material.id, 0)
        status = None
        if have <= 0 and (reorder or minimum):
            status = "out"
        elif minimum and have < minimum:
            status = "critical"
        elif reorder and have <= reorder:
            status = "low"
        elif maximum and have > maximum:
            status = "over"
        if status is None:
            continue
        suggest = None
        if status != "over" and maximum:
            suggest = max(round(maximum - have - coming, 4), 0)
        rows.append({"material": material, "unit": material.base_unit.code if material.base_unit else "", "available": have, "on_order": coming,
                     "reorder": reorder, "minimum": minimum, "maximum": maximum, "status": status, "label": LABELS[status], "suggest": suggest})
    rows.sort(key=lambda row: (ORDER[row["status"]], row["material"].name))
    return {"rows": rows, "unset": unset}


def alert_count():
    # Sidebar ke liye: kitne materials ko turant dhyan chahiye (Above maximum ginti me nahi)
    try:
        return len([row for row in stock_alerts()["rows"] if row["status"] != "over"])
    except Exception:
        return 0
