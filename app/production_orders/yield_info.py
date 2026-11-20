# C18: ordered vs good qty ka hisaab. (1) Order complete hone par "Short by X / Extra X" (2) naya order banate waqt product ka
# pichhle 3 completed orders ka average loss (hint). Naya DB table nahi: ProductionOutput.good_qty aur ProductionOrder.planned_qty se nikalte hain.
from app.models import ProductionOrder
from app.production_orders.source import customer_qty_of

EPS = 0.00005


def posted_output(order):
    # Order ka Posted (cancel nahi hua) output; ek order ka ek hi hota hai
    posted = [o for o in (order.outputs or []) if o.status == "Posted" and not o.is_deleted]
    return posted[-1] if posted else None


def short_info(order):
    """Completed order ke liye {"ordered", "good", "short", "extra", "unit"} (short / extra me se ek hi > 0). Output nahi to None."""
    out = posted_output(order)
    if not out:
        return None
    # Quotation se bana order: "ordered" = customer ne jitna manga (planner ne extra banane ko planned_qty badhaya ho to bhi kami tabhi jab customer ki qty poori na ho).
    # In-house / balance order: planned_qty hi.
    ordered = customer_qty_of(order)
    if ordered is None:
        ordered = order.planned_qty or 0
    diff = round(ordered - out.good_qty, 4)
    return {"ordered": ordered, "good": out.good_qty, "short": diff if diff > EPS else 0, "extra": -diff if diff < -EPS else 0,
            "unit": order.product.base_unit.code if order.product and order.product.base_unit else ""}


def learned_loss(product_id, count=3):
    """Is product ke pichhle `count` completed orders ka average loss %: (ordered - good) / ordered. Kam se kam 1 order ho tabhi, warna None.
    Zyada bana (good > ordered) to us order ka loss 0 ginte hain. Return {"pct": 8.3, "orders": 3}."""
    done = (ProductionOrder.query.filter(ProductionOrder.product_id == product_id, ProductionOrder.is_deleted == False,
                                         ProductionOrder.status == "Completed").order_by(ProductionOrder.id.desc()).all())
    losses = []
    for order in done:
        out = posted_output(order)
        if not out or not order.planned_qty:
            continue
        losses.append(max(0.0, (order.planned_qty - out.good_qty) / order.planned_qty * 100))
        if len(losses) == count:
            break
    if not losses:
        return None
    return {"pct": round(sum(losses) / len(losses), 1), "orders": len(losses)}
