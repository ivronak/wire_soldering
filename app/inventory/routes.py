# Stock pages (sirf padhne ke liye): Stock list (lot-wise + material-wise) aur ek lot ka poora ledger.
# Stock badalne ke rules app/inventory/posting.py me hain; yahan kuch save nahi hota.
from flask import render_template, Blueprint, abort, request
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
    "MRET_OUT": "Returned from production: left WIP",
    "MRET_IN": "Returned from production: back into store",
    "CONSUME": "Used up in production output",
}


def lot_unit(lot):
    return lot.unit_code


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

    # Transit me chal rahe transfers (maal source se nikla, destination me abhi nahi aaya)
    from app.models import StockTransferLine
    transit = {}
    for t_line in StockTransferLine.query.all():
        if t_line.transfer.status == "In transit" and not t_line.transfer.is_deleted:
            transit.setdefault(t_line.lot_id, []).append((round(t_line.qty, 4), round(t_line.value or 0, 2)))

    lot_rows = []
    for lot in StockLot.query.order_by(StockLot.id.desc()).all():
        row = {"lot": lot, "unit": lot_unit(lot), "waiting": 0, "available": 0, "rejected": 0, "wip": 0, "scrap": 0, "transit": 0, "value": 0, "where": [], "wh": {}}
        has_qc = lot.grn_line.final_qc is not None if lot.grn_line else False
        for warehouse_id, qty, value in sums.get(lot.id, []):
            if abs(qty) < 0.00005:
                continue
            warehouse = warehouses.get(warehouse_id)
            row["where"].append(warehouse.name if warehouse else "?")
            row["value"] += value
            wname = warehouse.name if warehouse else "?"
            wh_info = {"id": warehouse.id if warehouse else None, "name": wname, "type": warehouse.warehouse_type if warehouse else ""}
            # Har state ka warehouse naam (lot ek se zyada warehouse me ho sakta hai: jaise Available store me, Rejected QC Hold me)
            if warehouse is not None and warehouse.warehouse_type == "WIP":
                row["wip"] += qty
                row["wh"]["wip"] = wh_info
            elif warehouse is not None and warehouse.warehouse_type == "SCRAP":
                row["scrap"] += qty
                row["wh"]["scrap"] = wh_info
            elif warehouse is not None and warehouse.warehouse_type == "QC_HOLD":
                if has_qc:
                    row["rejected"] += qty
                    row["wh"]["rejected"] = wh_info
                else:
                    row["waiting"] += qty
                    row["wh"]["waiting"] = wh_info
            else:
                row["available"] += qty
                row["wh"]["available"] = wh_info
        for t_qty, t_value in transit.get(lot.id, []):
            row["transit"] += t_qty
            row["value"] += t_value
        row["value"] = round(row["value"], 2)
        # Poora use ho chuka lot (kisi bhi warehouse me kuch nahi bacha): list me default chhupa rehta hai, history ke liye rehta hai
        row["used_up"] = not (row["available"] > 0 or row["waiting"] > 0 or row["rejected"] > 0 or row["wip"] > 0 or row["transit"] > 0 or row["scrap"] > 0)
        lot_rows.append(row)

    # Material-wise jod (material + unit ek saath: alag units ka qty jodna galat hota)
    summary = {}
    for row in lot_rows:
        key = (row["lot"].raw_material_id, row["unit"])
        item = summary.setdefault(key, {"material": row["lot"].raw_material, "unit": row["unit"], "waiting": 0, "available": 0, "rejected": 0, "wip": 0, "scrap": 0, "transit": 0, "value": 0})
        for name in ("waiting", "available", "rejected", "wip", "scrap", "transit", "value"):
            item[name] += row[name]
    summary_rows = sorted(summary.values(), key=lambda item: item["material"].name if item["material"] else "")

    from app.inventory.alerts import stock_alerts
    return render_template("stock.html", active_nav="stock", lot_rows=lot_rows, summary_rows=summary_rows, alerts=stock_alerts())


# Lot history ki ek "event" = ek kaam (jaise QC pass). Ek kaam ki do rows (ek godown se minus, doosre me plus) ek line me dikhti hain.
EVENT_TITLES = {
    "GRN": "Goods received",
    "QC": "Quality check passed",
    "ISSUE": "Issued to production",
    "MRETURN": "Returned from production",
    "OUTPUT": "Used in production output",
    "RETURN": "Returned to vendor",
    "TRANSFER": "Stock transfer",
    "ADJUST": "Stock adjustment",
    "OPENING": "Opening stock",
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
        if ref_type == "TRANSFER":
            title = "Transfer dispatched" if leaving else "Transfer received"
            if cancelled:
                title = "Cancelled: transfer dispatched"
        if ref_type == "ADJUST" and first.note:
            title = "Stock adjustment (" + first.note + ")"
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
            tail = {"RETURN": " back to the vendor", "TRANSFER": " (on its way)"}.get(ref_type, "")
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
        elif wtype == "SCRAP":
            label, tone = "In scrap yard", "bad"
        elif wtype in ("RM", ""):
            label, tone = "Available to use", "good"
        else:
            label, tone = "Stored in " + wtype, "wip"
        where_now.append({"warehouse": warehouse.name if warehouse else "?", "label": label, "tone": tone,
                          "qty": round(qty, 4), "value": round(value, 2)})
    from app.models import StockTransfer, StockTransferLine
    for t_line in StockTransferLine.query.filter_by(lot_id=lot.id).all():
        if t_line.transfer.status == "In transit" and not t_line.transfer.is_deleted:
            where_now.append({"warehouse": t_line.transfer.from_warehouse.name + " → " + t_line.transfer.to_warehouse.name,
                              "label": "In transit (" + t_line.transfer.transfer_no + ")", "tone": "wip",
                              "qty": round(t_line.qty, 4), "value": round(t_line.value or 0, 2)})
    where_now.sort(key=lambda w: {"good": 0, "wip": 1, "wait": 2, "bad": 3}[w["tone"]])

    received = sum(m.qty for m in movements if m.movement_type in ("GRN_RECEIPT", "OPENING") and m.reverses_movement_id is None)
    return render_template("stock_lot.html", active_nav="stock", lot=lot, unit=unit,
                           events=build_events(movements, unit), where_now=where_now, received=received)


# ---------------- Stock valuation ----------------
@inventory_bp.route("/inventory/valuation")
def stock_valuation():
    # Stock ki value: material x jagah. Abhi har lot apne asli (PO rate wale) bhaav par hai, isliye "Unit cost" us jagah ke
    # lots ka average hai; "Cost layers" me har lot ka apna bhaav dikhta hai. Transit me chal raha maal alag jagah ("In transit") hai.
    from app.models import StockMovement as Movement, StockTransferLine, Warehouse

    wanted = (request.args.get("type") or "all").strip()
    sums = db.session.query(Movement.lot_id, Movement.warehouse_id, func.sum(Movement.qty), func.sum(Movement.value)).group_by(
        Movement.lot_id, Movement.warehouse_id).all()
    warehouses = {w.id: w for w in Warehouse.query.all()}
    lots = {lot.id: lot for lot in StockLot.query.all()}

    groups = {}

    def add(material_id, material, unit, place, wtype, lot, qty, value):
        key = (material_id, unit, place)
        item = groups.setdefault(key, {"material": material, "unit": unit, "place": place, "type": wtype, "qty": 0, "value": 0, "layers": []})
        item["qty"] += qty
        item["value"] += value
        item["layers"].append({"lot": lot.lot_code, "batch": lot.vendor_batch_no or "", "qty": qty, "value": value,
                               "cost": (value / qty) if qty else 0, "date": lot.created_at})

    for lot_id, warehouse_id, qty, value in sums:
        qty, value = round(qty or 0, 4), round(value or 0, 2)
        lot = lots.get(lot_id)
        warehouse = warehouses.get(warehouse_id)
        if lot is None or warehouse is None or abs(qty) < 0.00005:
            continue
        add(lot.raw_material_id, lot.raw_material, lot_unit(lot), warehouse.name, warehouse.warehouse_type, lot, qty, value)
    for t_line in StockTransferLine.query.all():
        transfer = t_line.transfer
        if transfer.status == "In transit" and not transfer.is_deleted and t_line.lot is not None:
            lot = t_line.lot
            add(lot.raw_material_id, lot.raw_material, lot_unit(lot), "In transit", "TRANSIT", lot, round(t_line.qty, 4), round(t_line.value or 0, 2))

    all_rows = sorted(groups.values(), key=lambda g: ((g["material"].name if g["material"] else ""), g["place"]))
    types = sorted({row["type"] for row in all_rows})
    rows = [row for row in all_rows if wanted == "all" or row["type"] == wanted]
    total_value = round(sum(row["value"] for row in all_rows), 2)
    transit_value = round(sum(row["value"] for row in all_rows if row["type"] == "TRANSIT"), 2)

    # Material-wise card: ek material = ek card, uske andar jagah-wise (warehouse) hissa. Bada value pehle.
    mats = {}
    for row in rows:
        key = (row["material"].id if row["material"] else 0, row["unit"])
        item = mats.setdefault(key, {"material": row["material"], "unit": row["unit"], "qty": 0, "value": 0, "places": []})
        item["qty"] += row["qty"]
        item["value"] += row["value"]
        item["places"].append(row)
    materials = sorted(mats.values(), key=lambda m: -m["value"])
    # "Paisa kahan pada hai": warehouse type-wise value (upar ki rangeen patti)
    by_type = {}
    for row in all_rows:
        by_type[row["type"]] = by_type.get(row["type"], 0) + row["value"]
    by_type = sorted(([t, round(v, 2)] for t, v in by_type.items() if v > 0), key=lambda x: -x[1])
    return render_template("stock_valuation.html", active_nav="valuation", materials=materials, types=types, wanted=wanted, by_type=by_type,
                           total_value=total_value, transit_value=transit_value, item_count=len({(r["material"].id if r["material"] else 0) for r in all_rows}))
