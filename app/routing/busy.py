# C8 / C11: machine "busy" hai ya nahi — kisi doosre order ka stage (In progress / On hold) us machine par abhi chal raha ho to naya stage
# us machine par Start nahi hota. Free hone ka andaza: started_at + planned_hours + ab tak ka hold time.
# Sirf padhta hai, kuch save nahi karta. Use: routing.routes (stage_machine_problem, routing_start).
from datetime import timedelta

from app.extensions import db
from app.models import ProductionOrder, ProductionOrderStage, ProductionOrderStageMachine
from app.production_orders.scheduler import now_ist


def free_at(stage):
    # Chal rahe stage ke khatam hone ka andaza (datetime) ya None (hold par ho / plan ke ghante pata nahi)
    if stage.status != "In progress" or not stage.started_at or not stage.planned_hours:
        return None
    return stage.started_at + timedelta(hours=stage.planned_hours, minutes=stage.hold_minutes or 0)


def busy_machines(order, stage):
    """{machine_id: {"prod_no", "stage_name", "on_hold", "free_at", "text"}} — un machines ki jaankari jinpar DOOSRE order ka stage abhi
    In progress / On hold hai. Apne hi order ke stages ginte nahi."""
    rows = (db.session.query(ProductionOrderStageMachine, ProductionOrderStage, ProductionOrder)
            .join(ProductionOrderStage, ProductionOrderStage.id == ProductionOrderStageMachine.stage_id)
            .join(ProductionOrder, ProductionOrder.id == ProductionOrderStage.production_order_id)
            .filter(ProductionOrderStage.status.in_(("In progress", "On hold")), ProductionOrderStage.id != stage.id,
                    ProductionOrder.id != order.id, ProductionOrder.is_deleted == False, ProductionOrder.status == "In production")
            .all())
    now = now_ist()
    out = {}
    for machine_row, other_stage, other_order in rows:
        when = free_at(other_stage)
        if other_stage.status == "On hold":
            text = f"busy with {other_order.prod_no} (on hold)"
        elif when is None:
            text = f"busy with {other_order.prod_no}"
        elif when <= now:
            text = f"busy with {other_order.prod_no} (running longer than planned)"
        else:
            text = f"busy with {other_order.prod_no}, free about {when.strftime('%H:%M') if when.date() == now.date() else when.strftime('%d %b %H:%M')}"
        info = {"prod_no": other_order.prod_no, "stage_name": other_stage.stage_name, "on_hold": other_stage.status == "On hold", "free_at": when, "text": text}
        # Ek machine par do rows aayein to jo pehle free hoga wahi dikhao
        old = out.get(machine_row.machine_id)
        if old is None or (when is not None and (old["free_at"] is None or when < old["free_at"])):
            out[machine_row.machine_id] = info
    return out
