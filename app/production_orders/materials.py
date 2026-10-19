# Production queue ke har order ka raw material check: store me stock hai? nahi to kisi PO me aa raha hai? ya kharidna padega?
# Sirf padhta hai, kuch save / lock nahi karta (soft reservation): queue me aage wale order ko stock pehle milta hai,
# peeche wale ko bacha hua. Stock aur "PO me aana baaki" inventory/alerts.py ke helper se, PO ki expected date PurchaseOrder se.
from app.inventory.alerts import store_stock_by_material
from app.models import PurchaseOrder

EPS = 1e-9


def _arrivals():
    # {raw_material_id: [[date | None, qty, po_no], ...]} — Open / Partial PO ki baaki qty, jaldi aane wali pehle (date na ho to aakhir me)
    out = {}
    pos = PurchaseOrder.query.filter(PurchaseOrder.is_deleted == False, PurchaseOrder.status.in_(["Open", "Partial"])).all()
    for po in pos:
        for line in po.lines:
            if line.remaining_qty > 0:
                out.setdefault(line.raw_material_id, []).append([po.expected_delivery_date, float(line.remaining_qty), po.po_no])
    for rows in out.values():
        rows.sort(key=lambda row: (row[0] is None, row[0] or 0))
    return out


def check_materials(ordered_orders):
    """ordered_orders: queue order me (pehle frozen). Wapas {order_id: {"status": "ok" | "coming" | "buy", "ready_date": date | None,
    "lines": [{"code", "name", "unit", "need", "from_stock", "from_po": [(po_no, qty, date)], "buy", "issued_all"}]}}.
    need = abhi issue hona baaki (required - issued). ok = sab stock me; coming = kuch PO se aayega; buy = PO me bhi nahi, kharidna padega."""
    pool = dict(store_stock_by_material())
    arrivals = _arrivals()
    result = {}
    for order in ordered_orders:
        lines = []
        status = "ok"
        ready_date = None
        for line in order.lines:
            rm = line.raw_material
            need = max(float(line.remaining_qty), 0.0)
            unit = rm.base_unit.code if rm and rm.base_unit else ""
            info = {"code": rm.code if rm else "—", "name": rm.name if rm else "", "unit": unit, "need": need,
                    "from_stock": 0.0, "from_po": [], "buy": 0.0, "issued_all": need <= EPS}
            if need > EPS:
                have = max(pool.get(line.raw_material_id, 0.0), 0.0)
                take = min(have, need)
                pool[line.raw_material_id] = have - take
                info["from_stock"] = take
                short = need - take
                queue = arrivals.get(line.raw_material_id, [])
                while short > EPS and queue:
                    when, qty, po_no = queue[0]
                    use = min(qty, short)
                    info["from_po"].append((po_no, use, when))
                    if when and (ready_date is None or when > ready_date):
                        ready_date = when
                    short -= use
                    if qty - use <= EPS:
                        queue.pop(0)
                    else:
                        queue[0][1] = qty - use
                info["buy"] = max(short, 0.0)
                if info["buy"] > EPS:
                    status = "buy"
                elif info["from_po"] and status != "buy":
                    status = "coming"
            lines.append(info)
        result[order.id] = {"status": status, "ready_date": ready_date, "lines": lines}
    return result
