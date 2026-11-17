# C8a / C9 (phase 1): batch stage (Melting furnace jaisa) ki machine me "Batch capacity (KG per melt)" + "Hours per batch" hai (Machines master).
# Yahan: order ke batch KG ke kitne melt (lot) banenge, aakhri melt kitna khali rahega (capacity waste), aur kaun sa doosra order (same alloy) isme mil sakta hai.
# Sirf padhta hai, kuch save nahi karta. Use: routing.routes (stage_plan, routing_start, routing_list).
import math

from app.extensions import db
from app.models import Machines, ProductionOrder


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
            if other_stage is None or other_stage.status != "Pending" or signature is None:
                continue
            other_kg = round((other.planned_qty or 0) * (other.unit_weight or 0), 3)
            if other_kg <= unused + 0.0005 and melt_signature(other, stage.work_stage_id) == signature:
                suggest.append({"prod_no": other.prod_no, "kg": other_kg})
    return {"cap": cap, "hours": info["hours"], "machine": info["machine"], "lots": lots, "unused_kg": unused, "suggest": suggest}
