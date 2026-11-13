# 30-din ka forward material plan (client change #3, MRP): har material ka stock + aane wale PO - queue ke orders ka maal = kitna bachega / kami kab.
# Sirf padhta hai, kuch save nahi karta. Hisaab: store (RM) stock se shuru -> din ke hisaab se PO ka aana (+) aur order ki zaroorat (-).
# Order ki zaroorat us din jab uska stage shuru hota hai (recipe line stage se juda ho to us stage ki date, warna order ki start date).
import math
from datetime import timedelta

from app.inventory.alerts import store_stock_by_material
from app.models import Product, PurchaseOrder, RawMaterial
from app.production_orders.scheduler import live_schedule, today_ist

HORIZON_DAYS = 30
EPS = 1e-6
SOON_DAYS = 7          # "place PO before" itne din ke andar ho to "Place soon"
GRADE_RANK = {"A": 0, "B": 1, "C": 2}      # vendor grade ki pasand: A sabse pehle, bina grade wale sabse baad me


def _demand_date(order, line, schedule, today):
    # Is order line ka maal kis din chahiye: us stage ki start date, nahi to order ki start date, nahi to earliest date. Beeti tareekh = aaj.
    info = schedule.get(order.id)
    day = None
    if info:
        day = info["start"]
        if line.work_stage_id:
            for stage, window in zip(order.stages, info["windows"]):
                if stage.work_stage_id == line.work_stage_id:
                    day = window[0]
                    break
    if day is None:
        day = order.earliest_start_date or order.order_date or today
    return max(day, today)


def last_po_lines():
    # {material_id: (po, line)} — us material ki sabse nayi (Cancelled / Draft nahi) PO line. Supplier = us PO ka vendor; rate / tax / unit bhi yahin se.
    out = {}
    pos = (PurchaseOrder.query.filter(PurchaseOrder.is_deleted == False, PurchaseOrder.status.notin_(["Cancelled", "Draft"]))
           .order_by(PurchaseOrder.po_date, PurchaseOrder.id).all())
    for po in pos:
        for line in po.lines:
            out[line.raw_material_id] = (po, line)
    return out


def po_lines_by_vendor():
    # {material_id: {vendor_id: (po, line)}} — us material ko jis-jis vendor se kharida (Cancelled / Draft PO nahi); har vendor ki sabse nayi line.
    # Rate / tax / unit isi line se aate hain, isliye sirf pehle kharide hue vendors hi suggest ho sakte hain.
    out = {}
    pos = (PurchaseOrder.query.filter(PurchaseOrder.is_deleted == False, PurchaseOrder.status.notin_(["Cancelled", "Draft"]))
           .order_by(PurchaseOrder.po_date, PurchaseOrder.id).all())
    for po in pos:
        for line in po.lines:
            out.setdefault(line.raw_material_id, {})[po.vendor_id] = (po, line)
    return out


def vendor_options(by_vendor):
    # Ek material ke vendors ki list, sabse achha pehle: chalu vendor, phir Grade A -> B -> C -> bina grade, barabar grade me sabse nayi PO wala.
    opts = [{"vendor": po.vendor, "po": po, "line": line} for po, line in by_vendor.values() if po.vendor is not None]
    opts.sort(key=lambda o: (0 if (o["vendor"].is_active and not o["vendor"].is_deleted) else 1, GRADE_RANK.get(o["vendor"].grade, 3),
                             -o["po"].po_date.toordinal(), -o["po"].id))
    return opts


def draft_po_by_material():
    # {material_id: po_no} — jo material kisi Draft PO me pehle se hai (dobara PO na ban jaye)
    out = {}
    for po in PurchaseOrder.query.filter(PurchaseOrder.is_deleted == False, PurchaseOrder.status == "Draft").order_by(PurchaseOrder.id).all():
        for line in po.lines:
            out.setdefault(line.raw_material_id, po.po_no)
    return out


def material_plan(today=None, picks=None):
    """picks = {material_id: vendor_id} — user ne dropdown se jo vendor chuna (nahi to Grade-A wala suggestion). Wapas {"rows": [...], "kpi": {...}, "today", "end"}. Har row = ek material: stock, 30 din ki zaroorat, aane wala maal, pehli kami ki date,
    kitni kami, vendor + lead time, "PO kab tak dalo", aur timeline (date-wise balance)."""
    today = today or today_ist()
    end = today + timedelta(days=HORIZON_DAYS)
    ordered, _materials, schedule = live_schedule(today)
    stock = store_stock_by_material()
    vendor_lines = po_lines_by_vendor()
    # In-house material (jaise Flux): {raw_material_id: Product} — iski kami PO se nahi, apna production order bana kar poori hoti hai (client meeting 2, #9)
    made_by = {p.output_rm_id: p for p in Product.query.filter(Product.output_rm_id.isnot(None), Product.is_deleted == False).all()}

    events = {}        # {material_id: [(date, order_of_day, kind, ref, qty)]}  qty signed; order_of_day: pehle aamad (0) phir zaroorat (1)
    undated = {}       # {material_id: qty} — expected date wala nahi PO
    overdue = {}       # {material_id: [po_no]} — expected date beet chuki
    for po in PurchaseOrder.query.filter(PurchaseOrder.is_deleted == False, PurchaseOrder.status.in_(["Open", "Partial"])).all():
        for line in po.lines:
            qty = float(line.remaining_qty)
            if qty <= EPS:
                continue
            when = po.expected_delivery_date
            if when is None:
                undated[line.raw_material_id] = undated.get(line.raw_material_id, 0.0) + qty
                continue
            if when < today:
                overdue.setdefault(line.raw_material_id, []).append(po.po_no)
                when = today
            if when <= end:
                events.setdefault(line.raw_material_id, []).append((when, 0, "arrive", po.po_no, qty))
    for order in ordered:
        # Queue me us in-house product ka order ho to uska output us din "aane wala maal" hai (jis din uska aakhri stage khatam)
        if order.product is not None and order.product.output_rm_id and order.status in ("Released", "In production"):
            info = schedule.get(order.id)
            batch_kg = float((order.planned_qty or 0) * (order.unit_weight or 1))
            if info and info["windows"] and batch_kg > EPS:
                when = max(info["windows"][-1][1], today)
                if when <= end:
                    events.setdefault(order.product.output_rm_id, []).append((when, 0, "arrive", order.prod_no, batch_kg))
        for line in order.lines:
            need = float(line.open_demand_qty)          # zaroorat + order ka allowance (stage ki use likh di to 0)
            if need <= EPS:
                continue
            when = _demand_date(order, line, schedule, today)
            if when <= end:
                events.setdefault(line.raw_material_id, []).append((when, 1, "need", order.prod_no, -need))

    rows = []
    material_ids = set(events) | {m for m, q in stock.items() if q > EPS} | set(undated)
    for material in RawMaterial.query.filter(RawMaterial.id.in_(material_ids), RawMaterial.is_deleted == False).order_by(RawMaterial.name).all():
        have = float(stock.get(material.id, 0.0))
        balance = have
        lowest = have
        short_date = None
        timeline = [{"date": today, "kind": "stock", "ref": "In store now", "qty": have, "balance": have}]
        need_total = coming_total = 0.0
        for when, _order, kind, ref, qty in sorted(events.get(material.id, []), key=lambda e: (e[0], e[1], e[3])):
            balance += qty
            if qty < 0:
                need_total += -qty
            else:
                coming_total += qty
            timeline.append({"date": when, "kind": kind, "ref": ref, "qty": qty, "balance": balance})
            if balance < lowest:
                lowest = balance
            if balance < -EPS and short_date is None:
                short_date = when
        if need_total <= EPS and not undated.get(material.id) and not coming_total:
            continue          # 30 din me is material ka koi kaam nahi
        shortage = round(max(-lowest, 0.0), 4) if short_date else 0.0
        maker = made_by.get(material.id)
        options = [] if maker else vendor_options(vendor_lines.get(material.id, {}))
        auto = options[0] if options else None
        chosen = auto
        if picks and options:
            chosen = next((o for o in options if o["vendor"].id == picks.get(material.id)), auto)
        vendor = chosen["vendor"] if chosen else None
        lead = vendor.lead_time_days if vendor is not None else None
        place_by = None
        urgency = None
        days_late = 0
        if short_date and maker is not None:
            urgency = "make"
        elif short_date:
            if lead is None:
                urgency = "no_lead"
            else:
                place_by = short_date - timedelta(days=lead)
                if place_by < today:
                    urgency, days_late = "late", (today - place_by).days
                elif place_by <= today + timedelta(days=SOON_DAYS):
                    urgency = "soon"
                else:
                    urgency = "plan"
        rows.append({"material": material, "unit": material.base_unit.code if material.base_unit else "", "have": round(have, 4),
                     "need": round(need_total, 4), "coming": round(coming_total, 4), "undated": round(undated.get(material.id, 0.0), 4),
                     "overdue": overdue.get(material.id, []), "end_balance": round(balance, 4), "short_date": short_date, "shortage": shortage,
                     "vendor": vendor, "lead": lead, "place_by": place_by, "urgency": urgency, "days_late": days_late, "timeline": timeline,
                     "last_line": chosen["line"] if chosen else None, "vendor_options": options, "auto_vendor_id": auto["vendor"].id if auto else None,
                     "orders": sorted({e["ref"] for e in timeline if e["kind"] == "need"}), "maker": maker})

    rank = {"late": 0, "make": 1, "soon": 2, "no_lead": 3, "plan": 4, None: 5}
    rows.sort(key=lambda r: (rank[r["urgency"]], r["short_date"] or end, r["material"].name))
    kpi = {"short": len([r for r in rows if r["short_date"]]), "late": len([r for r in rows if r["urgency"] == "late"]),
           "soon": len([r for r in rows if r["urgency"] == "soon"]), "no_lead": len([r for r in rows if r["urgency"] == "no_lead"]),
           "undated": len([r for r in rows if r["undated"] > EPS]), "overdue": len([r for r in rows if r["overdue"]]), "orders": len(ordered), "materials": len(rows)}
    return {"rows": rows, "kpi": kpi, "today": today, "end": end, "suggested": suggested_pos(rows, today), "no_supplier": [r for r in rows if r["short_date"] and r["vendor"] is None and r["maker"] is None]}


def suggested_qty(shortage):
    # Kami ko 2 decimal tak upar round (180.001 -> 180.01), taaki PO me kami se kam na ho
    return math.ceil(round(shortage * 100, 6)) / 100


def suggested_pos(rows, today):
    """Kami wale materials ko vendor ke hisaab se jodo: har vendor ke liye ek PO ka suggestion (client change #3: ek consolidated PO kai orders ke liye).
    Vendor = Grade A pehle (ya user ka chuna hua, material_plan ke picks se).
    Wapas [{vendor, expected, lines: [{row, qty, draft_po}], late}]. expected = aaj + vendor ka lead time (pata ho to); late = kami ki date tak nahi pahunchega."""
    drafts = draft_po_by_material()
    groups = {}
    for r in rows:
        if not r["short_date"] or r["vendor"] is None or r["last_line"] is None:
            continue
        group = groups.setdefault(r["vendor"].id, {"vendor": r["vendor"], "lines": []})
        group["lines"].append({"row": r, "qty": suggested_qty(r["shortage"]), "draft_po": drafts.get(r["material"].id)})
    out = []
    for group in groups.values():
        lead = group["vendor"].lead_time_days
        group["expected"] = today + timedelta(days=lead) if lead is not None else None
        group["late"] = bool(group["expected"] and any(line["row"]["short_date"] < group["expected"] for line in group["lines"]))
        group["open_lines"] = [line for line in group["lines"] if not line["draft_po"]]
        out.append(group)
    out.sort(key=lambda g: g["vendor"].name)
    return out
