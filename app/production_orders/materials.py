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
    """ordered_orders: queue order me (pehle frozen). Wapas {order_id: {"status": "ok" | "making" | "coming" | "buy", "ready_date": date | None,
    "make_behind": [{"name", "prod_no"}],
    "lines": [{"code", "name", "unit", "need", "from_stock", "from_po": [(po_no, qty, date)], "from_make": [(prod_no, qty, behind)], "buy", "issued_all"}]}}.
    need = abhi issue hona baaki (required - issued). ok = sab stock me; coming = kuch PO se aayega; buy = PO me bhi nahi, kharidna padega.
    C6 / G9: in-house material (jaise Flux) ka apna make-order queue me ho to wo kami poori karta hai: status "making" ("Will be made by PROD-X"),
    kharidna nahi. behind = wo make-order queue me is order ke PEECHE hai (Flux baad me banega) -> make_behind me jaata hai, red warning ke liye."""
    pool = dict(store_stock_by_material())
    arrivals = _arrivals()
    # In-house make orders: {raw_material_id: [[queue index, prod_no, bachi qty]]} — queue ke order me; Draft / Released / In production hi (poora hua to stock me aa chuka)
    makers = {}
    for index, other in enumerate(ordered_orders):
        product = other.product
        if product is not None and product.output_rm_id and other.status in ("Draft", "Released", "In production"):
            makers.setdefault(product.output_rm_id, []).append([index, other.prod_no, float((other.planned_qty or 0) * (other.unit_weight or 1))])
    result = {}
    for position, order in enumerate(ordered_orders):
        lines = []
        status = "ok"
        make_behind = []
        ready_date = None
        for line in order.lines:
            rm = line.raw_material
            need = max(float(line.remaining_qty), 0.0)
            unit = rm.base_unit.code if rm and rm.base_unit else ""
            info = {"code": rm.code if rm else "—", "name": rm.name if rm else "", "unit": unit, "need": need,
                    "from_stock": 0.0, "from_po": [], "from_make": [], "buy": 0.0, "issued_all": need <= EPS}
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
                # Bacha hua kami: pehle us in-house maal ke make-order se (khud ka order nahi), queue ke order me
                for maker in makers.get(line.raw_material_id, []):
                    if short <= EPS:
                        break
                    if maker[0] == position or maker[2] <= EPS:
                        continue
                    use = min(maker[2], short)
                    maker[2] -= use
                    short -= use
                    behind = maker[0] > position
                    info["from_make"].append((maker[1], use, behind))
                    if behind:
                        make_behind.append({"name": info["name"], "prod_no": maker[1]})
                info["buy"] = max(short, 0.0)
                if info["buy"] > EPS:
                    status = "buy"
                elif info["from_po"] and status != "buy":
                    status = "coming"
                elif info["from_make"] and status == "ok":
                    status = "making"
            lines.append(info)
        result[order.id] = {"status": status, "ready_date": ready_date, "lines": lines, "make_behind": make_behind}
    return result
