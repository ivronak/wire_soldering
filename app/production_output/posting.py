# Production output ka stock hisaab (sirf yahi file stock badalti hai, routes nahi):
#   Post   -> order ke WIP me bacha saara RM "use" ho jaata hai (ledger: CONSUME, value ke saath),
#             Good maal FG warehouse me (FG batch, cost = use hue RM ki value / Good qty), Scrap, Scrap warehouse me (cost 0).
#   Cancel -> sab ulti rows; sirf tab jab FG batch ko abhi kisi ne chheda nahi (aage Sales me dispatch hone par cancel nahi).
from app.extensions import db
from app.inventory.money import q2, q4, value_for_out
from app.inventory.posting import InventoryError, add_movement, balance, next_lot_code, reverse_document, rm_warehouse_of, wip_warehouse_for
from app.models import FGBatch, FGMovement, StockLot, StockMovement, Warehouse


def wip_lines(order):
    # [(issue_line, net_qty)] — Posted issues ki wo lot-lines jinme production ke paas maal bacha hai (issue - return)
    rows = []
    for issue in sorted(order.issues, key=lambda i: i.id):
        if issue.is_deleted or issue.status != "Posted":
            continue
        for line in issue.lines:
            net = q4(line.qty - line.returned_qty)
            if net > 0.00005:
                rows.append((line, net))
    return rows


def material_table(order):
    # Form ke liye: har material ka planned (recipe) vs production ko diya gaya (issue - return), aur uski value
    table = []
    for order_line in order.lines:
        rm = order_line.raw_material
        mine = [(line, n) for line, n in wip_lines(order) if line.production_order_line_id == order_line.id]
        net = sum(n for _line, n in mine)
        value = 0.0
        for line, n in mine:                       # abhi ki WIP value (post par yahi cost banegi)
            lot = line.lot
            wip = wip_warehouse_for(rm_warehouse_of(lot))
            wq, wv = balance(lot.id, wip.id)
            value += value_for_out(wq, wv, n)
        left = round(max(net - order_line.used_qty, 0), 4) if order_line.used_qty is not None else 0
        table.append({"name": rm.name if rm else "", "code": rm.code if rm else "", "unit": rm.base_unit.code if rm and rm.base_unit else "",
                      "planned": order_line.required_qty, "issued": round(net, 4), "value": q2(value),
                      "used": order_line.used_qty, "leftover": left if left > 0.00005 else 0})
    return table


def packed_lines(order):
    # Spooling / Packing stage me jo packing material (spool, box ...) gina gaya: [{name, unit, qty}]. Ye FG ki ginti dikhane ke liye hai
    # (jaise "1000 PCS spool, 20 BOX"); stock ka hisaab material_table / post_output se hi hota hai.
    rows = []
    for order_line in order.lines:
        if not order_line.is_packing or order_line.used_qty is None:
            continue
        rm = order_line.raw_material
        rows.append({"name": rm.name if rm else "", "unit": rm.base_unit.code if rm and rm.base_unit else "", "qty": order_line.used_qty,
                     "kg_per_pack": order_line.kg_per_pack})
    return rows


def leftover_rows(order):
    # [(order_line, qty)] — stage me use likhne ke baad bhi production (WIP) me bacha maal. Output se pehle ye store me wapas aana chahiye.
    # Jis line ki use likhi nahi (purane orders / maal baad me issue hua) uska kuch nahi maanga jaata: pehle jaisa, output par saara use.
    rows = []
    for order_line in order.lines:
        if order_line.used_qty is None:
            continue
        net = sum(n for line, n in wip_lines(order) if line.production_order_line_id == order_line.id)
        extra = round(net - order_line.used_qty, 4)
        if extra > 0.00005:
            rows.append((order_line, extra))
    return rows


def leftover_message(order):
    # Output rokne ka saaf sandesh (khaali string = koi leftover nahi)
    parts = []
    for order_line, extra in leftover_rows(order):
        rm = order_line.raw_material
        parts.append(f"{extra:g} {rm.base_unit.code if rm and rm.base_unit else ''} of {rm.name if rm else 'material'}".replace("  ", " "))
    if not parts:
        return ""
    return ("Return the unused material to the store before recording the output (Material issue, Return): " + "; ".join(parts) + ".")


def _warehouse(branch_id, wtype):
    warehouse = Warehouse.query.filter_by(branch_id=branch_id, warehouse_type=wtype, is_active=True, is_deleted=False).order_by(Warehouse.id).first()
    if warehouse is None:
        label = {"FG": "Finished goods (FG)", "SCRAP": "Scrap"}.get(wtype, wtype)
        raise InventoryError(f"There is no active {label} warehouse for this branch. Create one in Warehouses first.")
    return warehouse


def fg_warehouse_for(order):
    """Is order ka Good maal jis FG warehouse me jayega (RM ki WIP warehouse ki branch ka). Form ko rack ki list dikhane ke liye bhi yahi chahiye."""
    rows = wip_lines(order)
    if not rows:
        raise InventoryError("No material is in production for this order, so there is nothing to use up.")
    wip = wip_warehouse_for(rm_warehouse_of(rows[0][0].lot))
    return _warehouse(wip.branch_id, "FG")


def post_output(output, order, rack_id=None):
    """RM use + FG / Scrap stock. InventoryError uthata hai (caller rollback karta hai). rack_id = Good batch ka rack (optional)."""
    db.session.flush()
    rows = wip_lines(order)
    if not rows:
        raise InventoryError("No material is in production for this order, so there is nothing to use up.")
    blocked = leftover_message(order)
    if blocked:
        raise InventoryError(blocked)
    total_value = 0.0
    branch_id = None
    for line, net in rows:
        lot = line.lot
        store = rm_warehouse_of(lot)
        wip = wip_warehouse_for(store)
        branch_id = wip.branch_id
        wip_qty, wip_value = balance(lot.id, wip.id)
        if wip_qty + 0.00005 < net:
            raise InventoryError(f"Not enough {lot.lot_code} in {wip.name}: {wip_qty:g} is there but {net:g} was issued to this order.")
        value = value_for_out(wip_qty, wip_value, net)
        add_movement(lot, wip, output.output_date, "CONSUME", -net, -value, "OUTPUT", output.id, output.output_no, line.id)
        total_value += value
    scrap_warehouse = _warehouse(branch_id, "SCRAP") if output.scrap_qty > 0 else None
    output.total_value = q2(total_value)
    output.unit_cost = round(total_value / output.good_qty, 4) if output.good_qty else 0

    own_rm = order.product.output_rm if order.product else None
    if own_rm is not None:
        # In-house product (jaise Flux): Good maal FG me nahi, us Raw Material ke naye lot me store (RM) warehouse me. Wahan se wire ke order me issue hota hai.
        store = _warehouse(branch_id, "RM")
        lot = StockLot(lot_code=next_lot_code(), grn_line_id=None, source="OWN", raw_material_id=own_rm.id, unit_id=own_rm.base_unit_id,
                       vendor_batch_no=output.batch_no)
        db.session.add(lot)
        db.session.flush()
        add_movement(lot, store, output.output_date, "OWN_IN", output.good_qty, output.total_value, "OWNMADE", output.id, output.output_no, "1",
                     note=f"Made in house: {order.prod_no}")
    else:
        fg_warehouse = _warehouse(branch_id, "FG")
        batch = FGBatch(batch_no=output.batch_no, kind="FG", product_id=order.product_id, production_order_id=order.id, output=output,
                        mfg_date=output.output_date, unit_cost=output.unit_cost, rack_id=rack_id)
        db.session.add(batch)
        db.session.flush()
        db.session.add(FGMovement(batch_id=batch.id, warehouse_id=fg_warehouse.id, movement_date=output.output_date, movement_type="OUTPUT_IN",
                                  qty=q4(output.good_qty), value=output.total_value, ref_type="OUTPUT", ref_id=output.id, ref_no=output.output_no))
    if scrap_warehouse is not None:
        scrap_batch = FGBatch(batch_no=output.batch_no + "-S", kind="SCRAP", product_id=order.product_id, production_order_id=order.id, output=output,
                              mfg_date=output.output_date, unit_cost=0)
        db.session.add(scrap_batch)
        db.session.flush()
        db.session.add(FGMovement(batch_id=scrap_batch.id, warehouse_id=scrap_warehouse.id, movement_date=output.output_date, movement_type="OUTPUT_IN",
                                  qty=q4(output.scrap_qty), value=0, ref_type="OUTPUT", ref_id=output.id, ref_no=output.output_no))
    db.session.flush()


def cancel_output(output):
    # In-house product (Flux): uska lot abhi pura store me ho (kisi order me issue na hua ho), tabhi cancel
    for move in StockMovement.query.filter_by(ref_type="OWNMADE", ref_id=output.id, movement_type="OWN_IN").filter(StockMovement.reverses_movement_id.is_(None)).all():
        qty_now, _value = balance(move.lot_id, move.warehouse_id)
        if qty_now + 0.00005 < move.qty:
            raise InventoryError(f"Cannot cancel: some of {move.lot.lot_code} ({move.raw_material.name}) has already been issued to an order.")
    # Pehle jaanch: FG / Scrap batch ka maal abhi pura maujood ho (kisi ne nahi nikala)
    for batch in output.batches:
        booked = sum(m.qty for m in batch.movements if m.movement_type == "OUTPUT_IN" and m.reverses_movement_id is None)
        qty_now, _value = batch.balance
        if qty_now + 0.00005 < booked:
            raise InventoryError(f"Cannot cancel: some of batch {batch.batch_no} has already been used or sent out.")
    reverse_document("OUTPUT", output.id, "Reversal: production output cancelled")          # RM WIP me wapas
    reverse_document("OWNMADE", output.id, "Reversal: production output cancelled")         # in-house maal ka lot wapas
    for batch in output.batches:
        for move in list(batch.movements):
            if move.reverses_movement_id is not None or move.ref_type != "OUTPUT":
                continue
            if FGMovement.query.filter_by(reverses_movement_id=move.id).first() is not None:
                continue
            db.session.add(FGMovement(batch_id=move.batch_id, warehouse_id=move.warehouse_id, movement_date=move.movement_date,
                                      movement_type=move.movement_type, qty=q4(-move.qty), value=q2(-move.value), ref_type=move.ref_type,
                                      ref_id=move.ref_id, ref_no=move.ref_no, reverses_movement_id=move.id,
                                      note="Reversal: production output cancelled"))
    db.session.flush()
