# C8a / C9 (phase 1): batch stage (Melting furnace jaisa) ki machine me "Batch capacity (KG per melt)" + "Hours per batch" hai (Machines master).
# Yahan: order ke batch KG ke kitne melt (lot) banenge, aakhri melt kitna khali rahega (capacity waste), aur kaun sa doosra order (same alloy) isme mil sakta hai.
# Sirf padhta hai, kuch save nahi karta. Use: routing.routes (stage_plan, routing_start, routing_list).
import math

from app.extensions import db
from app.models import Machines, MeltGroup, ProductionOrder
from app.production_orders.scheduler import today_ist


def batch_info(stage):
    """Is stage ki machines me sabse badi batch capacity: {"kg", "hours", "machine"} ya None (kisi machine me batch numbers nahi bhare)."""
    best = None
    for row in stage.machines:
        machine = db.session.get(Machines, row.machine_id)
        if machine is None or not machine.batch_capacity_kg or not machine.hours_per_batch:
            continue
        if best is None or machine.batch_capacity_kg > best["kg"]:
            best = {"kg": machine.batch_capacity_kg, "hours": machine.hours_per_batch, "machine": machine.name}
    return best


def melt_signature(order, work_stage_id):
    """Alloy ki pehchaan: is stage ki material lines (raw material + stage ke kul material me uska hissa). Do orders ki signature barabar = same alloy
    (jaise dono 60/40). Hissa kul se naapte hain, isliye "extra for scrap %" lagne se signature nahi badalta. Alag alloy (50/50) ki signature alag
    aati hai, isliye wo kabhi suggest nahi hota."""
    lines = [l for l in order.lines if l.work_stage_id == work_stage_id]
    total = sum(l.required_qty or 0 for l in lines)
    if total <= 0:
        return None
    return tuple(sorted((l.raw_material_id, round(l.required_qty / total, 3)) for l in lines))


def melt_plan(order, stage, batch_kg):
    """Batch stage ke liye: {"cap", "hours", "machine", "lots": [KG ...], "unused_kg", "suggest": [{"prod_no", "kg"}]} ya None
    (stage batch nahi / batch capacity nahi bhari / batch KG nahi). unused_kg = melts ki kul capacity - order ka KG (0 = furnace poora bhara)."""
    if not (stage.work_stage and stage.work_stage.is_batch) or batch_kg <= 0:
        return None
    info = batch_info(stage)
    if info is None:
        return None
    cap = info["kg"]
    count = math.ceil(batch_kg / cap - 1e-9)
    lots, left = [], batch_kg
    for _ in range(count):
        kg = round(min(cap, left), 3)
        lots.append(kg)
        left = round(left - kg, 3)
    unused = round(count * cap - batch_kg, 3)
    suggest = []
    if unused > 0.0005:
        signature = melt_signature(order, stage.work_stage_id)
        others = ProductionOrder.query.filter(ProductionOrder.is_deleted == False, ProductionOrder.id != order.id,
                                              ProductionOrder.status.in_(("Draft", "Released", "In production"))).order_by(ProductionOrder.id).all()
        for other in others:
            other_stage = next((s for s in other.stages if s.work_stage_id == stage.work_stage_id), None)
            if other_stage is None or other_stage.status != "Pending" or signature is None or other_stage.melt_group_id is not None:
                continue
            other_kg = round((other.planned_qty or 0) * (other.unit_weight or 0), 3)
            if other_kg <= unused + 0.0005 and melt_signature(other, stage.work_stage_id) == signature:
                # in_production = routing page se abhi jod sakte hain; warna sirf suggestion (order abhi chalu nahi hua)
                suggest.append({"prod_no": other.prod_no, "kg": other_kg, "stage_id": other_stage.id, "in_production": other.status == "In production"})
    return {"cap": cap, "hours": info["hours"], "machine": info["machine"], "lots": lots, "unused_kg": unused, "suggest": suggest}


# ---------------- C9 phase 2: melt group (heat number) ----------------
def stage_kg(stage):
    # Is Melting stage ke order ka batch KG
    order = stage.production_order
    return round((order.planned_qty or 0) * (order.unit_weight or 0), 4)


def melt_members(stage):
    # Is stage ke melt ke saare stages (apna bhi). Group nahi hai to sirf apna.
    if stage.melt_group_id:
        return list(stage.melt_group.stages)
    return [stage]


def melt_kg(stage):
    # Poore melt ka KG (sab members ke order ka jod)
    return round(sum(stage_kg(member) for member in melt_members(stage)), 4)


def next_heat_no():
    # HT-2026-001: saal ke hisaab se
    year = today_ist().year
    count = MeltGroup.query.filter(MeltGroup.heat_no.like(f"HT-{year}-%")).count()
    return f"HT-{year}-{count + 1:03d}"


def ensure_melt_group(stage):
    # Is Melting stage ka group (nahi hai to naya, naye heat number ke saath). Commit caller karega.
    if stage.melt_group_id is None:
        group = MeltGroup(heat_no=next_heat_no(), work_stage_id=stage.work_stage_id)
        db.session.add(group)
        db.session.flush()
        stage.melt_group_id = group.id
        db.session.flush()
        db.session.refresh(stage)
    return stage.melt_group


def combine_error(stage, other):
    """Do Pending Melting stages ek melt me jud sakte hain? Nahi to wajah (English text, user ko dikhta hai), ho sakta ho to None."""
    if other.id == stage.id:
        return "A melt cannot be combined with itself."
    if stage.melt_group_id and stage.melt_group_id == other.melt_group_id:
        return f"{other.production_order.prod_no} is already in this melt."
    if other.melt_group_id is not None:
        return f"{other.production_order.prod_no} is already part of another melt ({other.melt_group.heat_no})."
    if stage.status != "Pending" or other.status != "Pending" or any(m.status != "Pending" for m in melt_members(stage)):
        return "Orders can be combined only before the melt starts."
    if stage.work_stage_id != other.work_stage_id or not (stage.work_stage and stage.work_stage.is_batch):
        return "Only the same batch stage (the furnace melt) can be combined."
    for member_stage in (stage, other):
        order = member_stage.production_order
        if order is None or order.is_deleted or order.status != "In production":
            return f"{order.prod_no if order else 'The order'} is not in production yet, so it cannot join a melt."
    if melt_signature(stage.production_order, stage.work_stage_id) != melt_signature(other.production_order, other.work_stage_id):
        return "These orders are not the same alloy, so they cannot share one melt."
    plan = melt_plan(stage.production_order, stage, melt_kg(stage))
    if plan is None:
        return "The furnace has no batch capacity set, so orders cannot be combined."
    if stage_kg(other) > plan["unused_kg"] + 0.0005:
        return f"{other.production_order.prod_no} ({stage_kg(other):g} KG) does not fit: only {plan['unused_kg']:g} KG of the furnace is free in this melt."
    return None
