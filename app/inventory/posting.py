# Stock kab, kitna, kahan badalta hai: SIRF isi file me likha hai (GRN / QC / Return ke routes yahin ke functions bulate hain).
#
# Rules (client ke feedback ke baad):
#   1. GRN post  -> har line ka naya LOT, poori received qty us branch ke QC Hold warehouse me (value = PO rate, "estimated").
#   2. Final QC  -> passed qty QC Hold se nikal ke PO ke warehouse (RM) me. Rejected qty QC Hold me hi rehti hai ("Rejected"),
#                   jab tak Purchase Return (rejected me se) usse vendor ko wapas na bheje.
#   3. Purchase Invoice stock nahi badalta (wo sirf vendor ka paisa hai).
#   4. Purchase Return -> "passed" ka maal RM warehouse se, "rejected" ka maal QC Hold se ghatata hai. Cancel = ulti rows.
#   5. Stock kabhi minus nahi: nikalne se pehle jaanch, kam ho to InventoryError.
# Ledger ki rows kabhi edit / delete nahi hoti (models.py ka listener rokta hai); galti = ulti (reversal) row.
from sqlalchemy import func

from app.extensions import db
from app.inventory.money import q2, q4, value_for_out
from app.models import StockLot, StockMovement, Warehouse


class InventoryError(Exception):
    pass


# ---------------- helpers ----------------
def hold_warehouse_for(po):
    # Delivery branch ka QC Hold warehouse (type QC_HOLD, active)
    branch_id = po.warehouse.branch_id if po.warehouse else None
    warehouse = Warehouse.query.filter_by(branch_id=branch_id, warehouse_type="QC_HOLD", is_active=True, is_deleted=False).order_by(Warehouse.id).first()
    if warehouse is None:
        raise InventoryError(f"The branch of {po.po_no} has no active QC Hold warehouse. Create one in Warehouses first.")
    return warehouse


def balance(lot_id, warehouse_id):
    # (qty, value) = is lot ka is warehouse me abhi kitna hai: rows ka SUM
    row = db.session.query(func.coalesce(func.sum(StockMovement.qty), 0), func.coalesce(func.sum(StockMovement.value), 0)).filter(
        StockMovement.lot_id == lot_id, StockMovement.warehouse_id == warehouse_id).one()
    return q4(row[0]), q2(row[1])


def _existing(ref_type, ref_id, line_key, movement_type):
    return StockMovement.query.filter(
        StockMovement.ref_type == ref_type, StockMovement.ref_id == ref_id, StockMovement.line_key == str(line_key),
        StockMovement.movement_type == movement_type, StockMovement.reverses_movement_id.is_(None)).first()


def add_movement(lot, warehouse, movement_date, movement_type, qty, value, ref_type, ref_id, ref_no, line_key, note=None):
    # Ek row likho. Wahi (document, line, type) pehle se likhi ho to dobara nahi likhta (double entry nahi).
    # Nikalne (qty < 0) se pehle on-hand jaanchta hai: stock minus nahi ho sakta.
    done = _existing(ref_type, ref_id, line_key, movement_type)
    if done is not None:
        return done
    qty = q4(qty)
    if qty < 0:
        on_hand, _value = balance(lot.id, warehouse.id)
        if on_hand + qty < -0.00005:
            raise InventoryError(f"Not enough stock: only {on_hand:g} of {lot.lot_code} is in {warehouse.name}, but {abs(qty):g} was needed.")
    movement = StockMovement(
        movement_date=movement_date, raw_material_id=lot.raw_material_id, warehouse_id=warehouse.id, lot_id=lot.id,
        movement_type=movement_type, qty=qty, value=q2(value), ref_type=ref_type, ref_id=ref_id, ref_no=ref_no,
        line_key=str(line_key), note=note)
    db.session.add(movement)
    db.session.flush()
    return movement


def _next_lot_code():
    count = StockLot.query.count()
    return f"LOT-{count + 1:04d}"


def lot_for(grn_line):
    # Is GRN line ka lot (nahi hai to banao)
    lot = StockLot.query.filter_by(grn_line_id=grn_line.id).first()
    if lot is None:
        po_line = grn_line.po_line
        lot = StockLot(lot_code=_next_lot_code(), grn_line_id=grn_line.id, raw_material_id=po_line.raw_material_id,
                       vendor_batch_no=grn_line.batch_lot_no)
        db.session.add(lot)
        db.session.flush()
    return lot


def rm_warehouse_of(lot):
    # Passed maal jahan gaya: us lot ki QC_IN row ka warehouse; nahi mila to PO ka warehouse
    row = StockMovement.query.filter_by(lot_id=lot.id, movement_type="QC_IN").first()
    if row is not None:
        return row.warehouse
    return lot.grn_line.grn.po.warehouse


# ---------------- 1. GRN post ----------------
def receive_grn(grn):
    # Post hui GRN ki har line: lot + QC Hold me +qty (value = qty x PO rate)
    po = grn.po
    hold = hold_warehouse_for(po)
    for grn_line in grn.lines:
        lot = lot_for(grn_line)
        value = q2(q4(grn_line.received_qty) * (grn_line.po_line.rate or 0))
        add_movement(lot, hold, grn.grn_date, "GRN_RECEIPT", grn_line.received_qty, value, "GRN", grn.id, grn.grn_no, grn_line.id)


# ---------------- 2. Final QC ----------------
def qc_passed_to_stock(inward_qc, grn_line):
    # Final QC (Draft nahi) ka passed qty: QC Hold se nikal ke PO ke warehouse me. Rejected qty yahin QC Hold me rehti hai.
    if inward_qc.status == "Draft" or (inward_qc.passed_qty or 0) <= 0:
        return
    grn = grn_line.grn
    po = grn.po
    hold = hold_warehouse_for(po)
    lot = lot_for(grn_line)
    # Purani GRN (inventory se pehle post hui) ka receipt abhi na bana ho to pehle wo
    value = q2(q4(grn_line.received_qty) * (grn_line.po_line.rate or 0))
    add_movement(lot, hold, grn.grn_date, "GRN_RECEIPT", grn_line.received_qty, value, "GRN", grn.id, grn.grn_no, grn_line.id)

    qty = q4(inward_qc.passed_qty)
    rem_qty, rem_value = balance(lot.id, hold.id)
    out_value = value_for_out(rem_qty, rem_value, qty)
    date_ = inward_qc.inspection_date
    add_movement(lot, hold, date_, "QC_OUT", -qty, -out_value, "QC", inward_qc.id, inward_qc.qc_no, grn_line.id)
    add_movement(lot, po.warehouse, date_, "QC_IN", qty, out_value, "QC", inward_qc.id, inward_qc.qc_no, grn_line.id)


# ---------------- 4. Purchase Return ----------------
def return_to_stock(purchase_return):
    # Return ki har line: "passed" ka maal RM warehouse se, "rejected" ka maal QC Hold se bahar
    db.session.flush()                 # nayi return lines ki id chahiye (line_key)
    for return_line in purchase_return.lines:
        invoice_line = return_line.invoice_line
        grn_line = invoice_line.grn_line
        lot = lot_for(grn_line)
        po = grn_line.grn.po
        warehouse = hold_warehouse_for(po) if (return_line.source or "passed") == "rejected" else rm_warehouse_of(lot)
        qty = q4(return_line.qty)
        rem_qty, rem_value = balance(lot.id, warehouse.id)
        out_value = value_for_out(rem_qty, rem_value, qty)
        add_movement(lot, warehouse, purchase_return.return_date, "PURCHASE_RETURN", -qty, -out_value,
                     "RETURN", purchase_return.id, purchase_return.pr_no, return_line.id)


def return_cancelled(purchase_return):
    reverse_document("RETURN", purchase_return.id, "Reversal: return cancelled")


def wip_warehouse_for(warehouse):
    # RM warehouse ki branch ka WIP warehouse (type WIP, active)
    wip = Warehouse.query.filter_by(branch_id=warehouse.branch_id, warehouse_type="WIP", is_active=True, is_deleted=False).order_by(Warehouse.id).first()
    if wip is None:
        raise InventoryError(f"The branch of {warehouse.name} has no active WIP warehouse. Create one in Warehouses first.")
    return wip


def available_lots(raw_material_id):
    # Is material ke wo lots jinka maal store (RM) me hai, purana lot pehle (FIFO). [(lot, warehouse, qty, value)]
    result = []
    for lot in StockLot.query.filter_by(raw_material_id=raw_material_id).order_by(StockLot.id).all():
        store = rm_warehouse_of(lot) if StockMovement.query.filter_by(lot_id=lot.id, movement_type="QC_IN").first() else None
        if store is None:
            continue
        qty, value = balance(lot.id, store.id)
        if qty > 0.00005:
            result.append((lot, store, qty, value))
    return result


def issue_to_wip(issue):
    # Material issue post: har line ka maal store se nikal ke WIP warehouse me (value ke saath). Lot ka naam saath chalta hai.
    db.session.flush()                 # nayi issue lines ki id chahiye (line_key)
    for line in issue.lines:
        lot = line.lot
        store = rm_warehouse_of(lot)
        wip = wip_warehouse_for(store)
        qty = q4(line.qty)
        rem_qty, rem_value = balance(lot.id, store.id)
        out_value = value_for_out(rem_qty, rem_value, qty)
        add_movement(lot, store, issue.issue_date, "ISSUE_OUT", -qty, -out_value, "ISSUE", issue.id, issue.issue_no, line.id)
        add_movement(lot, wip, issue.issue_date, "ISSUE_IN", qty, out_value, "ISSUE", issue.id, issue.issue_no, line.id)


def issue_cancelled(issue):
    reverse_document("ISSUE", issue.id, "Reversal: material issue cancelled")


def reverse_document(ref_type, ref_id, note):
    # Cancel: us document ki har movement ke liye ulti row (qty / value ka sign ulta). Pehle se ulti ho chuki ho to chhod do.
    rows = StockMovement.query.filter_by(ref_type=ref_type, ref_id=ref_id).filter(StockMovement.reverses_movement_id.is_(None)).all()
    for row in rows:
        if StockMovement.query.filter_by(reverses_movement_id=row.id).first() is not None:
            continue
        db.session.add(StockMovement(
            movement_date=row.movement_date, raw_material_id=row.raw_material_id, warehouse_id=row.warehouse_id, lot_id=row.lot_id,
            movement_type=row.movement_type, qty=q4(-row.qty), value=q2(-row.value), ref_type=row.ref_type, ref_id=row.ref_id,
            ref_no=row.ref_no, line_key=row.line_key, reverses_movement_id=row.id, note=note))
    db.session.flush()


# ---------------- purane documents ke liye ----------------
def backfill():
    # Inventory banne se pehle ke GRN / QC / Return ki rows banata hai (wahi functions, to wahi rules). Dobara chalao to double nahi hoga.
    from app.models import GRN, InwardQC, PurchaseReturn
    problems = []
    for grn in GRN.query.filter(GRN.is_deleted == False, GRN.status != "Draft").order_by(GRN.id).all():
        try:
            receive_grn(grn)
        except InventoryError as error:
            problems.append(f"{grn.grn_no}: {error}")
    for qc in InwardQC.query.filter(InwardQC.is_deleted == False, InwardQC.status != "Draft").order_by(InwardQC.id).all():
        try:
            qc_passed_to_stock(qc, qc.grn_line)
        except InventoryError as error:
            problems.append(f"{qc.qc_no}: {error}")
    for purchase_return in PurchaseReturn.query.filter(PurchaseReturn.is_deleted == False).order_by(PurchaseReturn.id).all():
        try:
            return_to_stock(purchase_return)
            if purchase_return.status == "Cancelled":
                return_cancelled(purchase_return)
        except InventoryError as error:
            problems.append(f"{purchase_return.pr_no}: {error}")
    db.session.commit()
    return problems
