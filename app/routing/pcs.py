# C15: Spooling ke baad maal PCS (spool) me ginte hain, KG sirf reference. Stages ki asli qty (qty_in / qty_out / scrap_qty) DB me KG me hi rehti hai
# (scheduler, yield, costing sab KG par); yahan sirf KG <-> PCS ka hisaab hai taaki form / table PCS dikha sake. Naya DB field sirf WorkStage.counts_pcs.
# Sirf PCS wale product me (unit KG nahi) aur jab order ke kisi stage par "Counted in pieces" tick ho; warna kuch nahi badalta (purana tareeka).


def is_pcs_product(order):
    unit = order.product.base_unit.code.upper() if order.product and order.product.base_unit else "KG"
    return unit not in ("KG", "KGS") and (order.unit_weight or 0) > 0


def pcs_start_stage(order):
    # Order ka pehla stage jis par PCS tick hai (Spooling); PCS product na ho ya tick na ho to None
    if not is_pcs_product(order):
        return None
    for stage in sorted(order.stages, key=lambda s: s.sort_order):
        if stage.work_stage and stage.work_stage.counts_pcs:
            return stage
    return None


def spools_made(order, stage):
    """Is stage ne kitne piece (spool) banaye: stage ki material lines me jo product ki apni unit (PCS) me hain unki used qty.
    Stage abhi Done nahi / ginti nahi likhi to None."""
    unit = order.product.base_unit.code.upper() if order.product and order.product.base_unit else ""
    total, found = 0.0, False
    for line in order.lines:
        if line.work_stage_id != stage.work_stage_id or line.used_qty is None or not line.raw_material or not line.raw_material.base_unit:
            continue
        if line.raw_material.base_unit.code.upper() == unit:
            total += line.used_qty
            found = True
    return round(total, 4) if found and total > 0 else None


def kg_per_piece(order, start):
    # Asli average KG per spool = Spooling ka good wire / bane hue spool. Ginti nahi likhi to product ka nominal weight (0.5 KG)
    made = spools_made(order, start) if start.status == "Done" else None
    if made and start.qty_out:
        return start.qty_out / made
    return order.unit_weight


def pcs_mode(order, stage):
    """Is stage ka PCS rup: None (KG hi) ya {"kind": "out"|"all", "w": nominal KG/pc, "wa": asli KG/pc, "start": Spooling stage}.
    kind "out" = Spooling khud: wire KG me aata hai, spool ginti (PCS) nikalti hai. kind "all" = Spooling ke baad ke stages: sab PCS me."""
    start = pcs_start_stage(order)
    if start is None:
        return None
    if stage.id == start.id:
        return {"kind": "out", "w": order.unit_weight, "wa": order.unit_weight, "start": start}
    if stage.sort_order > start.sort_order:
        return {"kind": "all", "w": order.unit_weight, "wa": kg_per_piece(order, start), "start": start}
    return None


def to_pcs(kg, mode):
    # KG -> PCS (gol, kyunki piece poore hote hain). Jab asli KG/pc pata ho tabhi sahi; nahi to nominal
    if kg is None or not mode or not mode["wa"]:
        return None
    return round(kg / mode["wa"], 2)
