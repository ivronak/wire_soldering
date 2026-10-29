# Production line ka live status: kaun sa order chal raha hai, kitna maal baaki, line kab tak busy / kab free.
# Order Queue -> Start karte waqt line chunne ke liye (client change #1, 2026-10-26).
import math
from datetime import timedelta

from app.models import ProductionLine, ProductionOrder


def line_board(today):
    # Har active line ka haal. Baaki KG = batch KG x (bache hue stages / kul stages); busy din = baaki KG / daily capacity (upar round).
    board = []
    lines = ProductionLine.query.filter_by(is_deleted=False, is_active=True).order_by(ProductionLine.code).all()
    for line in lines:
        running = ProductionOrder.query.filter_by(line_id=line.id, status="In production", is_deleted=False).order_by(ProductionOrder.id).all()
        items, left_total = [], 0.0
        for order in running:
            batch_kg = (order.planned_qty or 0) * (order.unit_weight or 1)
            stages = order.stages
            done = len([s for s in stages if s.status == "Done"])
            left = batch_kg * (1 - done / len(stages)) if stages else batch_kg
            left_total += left
            items.append({"prod_no": order.prod_no, "product": order.product.name if order.product else "", "batch_kg": round(batch_kg, 2),
                          "left_kg": round(left, 2), "done": done, "total": len(stages),
                          "ends": order.planned_end_date.strftime("%d %b") if order.planned_end_date else ""})
        busy_days = math.ceil(left_total / line.daily_capacity_kg - 1e-9) if left_total > 0.0001 else 0
        board.append({"id": line.id, "code": line.code, "name": line.name, "capacity": line.daily_capacity_kg, "handler": line.handler or "",
                      "machines": len(line.active_machines), "running": items, "left_kg": round(left_total, 2), "busy_days": busy_days,
                      "free_from": (today + timedelta(days=busy_days)).strftime("%d %b %Y")})
    return board
