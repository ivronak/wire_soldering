# Production order ka "source": ye order kis quotation ke liye bana hai, ya in-house stock ke liye (fix_list #11 / #12, 20 Nov 2026).
# Naya DB column nahi: QuotationLine.production_order_id (Finalize par set hota hai) se nikalte hain.
#   * Quotation se bana order  -> "quotation": quote_no (party ka naam nahi — plant ko party nahi dikhti) + customer_qty (customer ne jitna manga)
#   * Balance order (kami poori karne wala) -> original order ke quotation ka quote_no, par customer_qty None (uski qty kami jitni hi hai)
#   * Baaki (Production page ke form se bane) -> "inhouse": stock ke liye
# Order ki planned_qty = factory kitna BANAYEGI. customer_qty se zyada ho to fark "extra" hai jo FG stock me jaata hai.
from app.models import QuotationLine


def _line_by_order(order_ids):
    if not order_ids:
        return {}
    lines = QuotationLine.query.filter(QuotationLine.production_order_id.in_(list(order_ids))).all()
    return {line.production_order_id: line for line in lines}


def source_map(orders):
    """{order_id: {"kind": "quotation" | "inhouse", "quote_no": str | None, "customer_qty": float | None, "extra": float}} — list ke saare orders ke liye ek saath."""
    orders = list(orders)
    direct = _line_by_order({o.id for o in orders})
    # Balance order ka quotation = original order ka quotation
    original_ids = {o.balance_for_id for o in orders if o.id not in direct and o.balance_for_id}
    via_original = _line_by_order(original_ids)
    out = {}
    for order in orders:
        line = direct.get(order.id)
        customer_qty = line.qty if line is not None else None
        if line is None and order.balance_for_id:
            line = via_original.get(order.balance_for_id)
        if line is None:
            out[order.id] = {"kind": "inhouse", "quote_no": None, "customer_qty": None, "extra": 0.0}
            continue
        extra = round((order.planned_qty or 0) - customer_qty, 4) if customer_qty is not None else 0.0
        out[order.id] = {"kind": "quotation", "quote_no": line.quotation.quote_no if line.quotation else None,
                         "customer_qty": customer_qty, "extra": extra if extra > 0.00005 else 0.0}
    return out


def line_needs_order(line):
    """Kya ye quotation line abhi "Against quotation" order ke liye khuli hai: quotation Ordered, koi chalta production order juda nahi
    (Finalize me 'serve from stock' wali line, ya jis order ko cancel kar diya), aur maal abhi poora dispatch nahi hua."""
    from app.dispatch.stock import dispatched_qty, pending_qty
    quotation = line.quotation
    if quotation is None or quotation.is_deleted or quotation.status != "Ordered":
        return False
    linked = line.production_order
    if linked is not None and not linked.is_deleted and linked.status != "Cancelled":
        return False
    # Kuch dispatch ho chuka ho to line ki customer qty aur ab bacha hua alag ho jaata hai — aisi line ke liye order yahan se nahi (pura dispatch / stock se hi)
    return dispatched_qty(line) <= 0.00005 and pending_qty(line) > 0.00005


def open_quotation_lines():
    """{product_id: [{"line_id", "quote_no", "qty"}]} — form ke "Against quotation" picker ke liye. Sirf QT number (party ka naam nahi)."""
    from app.models import Quotation
    lines = (QuotationLine.query.join(Quotation, Quotation.id == QuotationLine.quotation_id)
             .filter(Quotation.is_deleted == False, Quotation.status == "Ordered").order_by(Quotation.quote_no, QuotationLine.id).all())
    out = {}
    for line in lines:
        if line_needs_order(line):
            out.setdefault(line.product_id, []).append({"line_id": line.id, "quote_no": line.quotation.quote_no, "qty": line.qty})
    return out


def customer_qty_of(order):
    """Is order se jude quotation line ki qty (customer ne jitna manga); quotation se seedha bana na ho to None."""
    line = QuotationLine.query.filter_by(production_order_id=order.id).first()
    return line.qty if line is not None else None
