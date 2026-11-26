# Dashboard "Overview" tab ka saara data. Plan: dashboard_flow_2026_11_26.md
# Sirf PADHTA hai, kuch save nahi karta. Har panel tabhi banta hai jab user ko us panel ke asli page ka View ho (backend par hi rok).
# Jahan ho sake wahi functions use kiye jo asli pages chalate hain (aging, accounts reports, machine board, stock alerts), taaki dono jagah ek hi jawab mile.
from datetime import date, timedelta

from flask import url_for
from sqlalchemy import func

from app.accounts.reports import movements, profit_loss
from app.aging.aging import BUCKET_LABELS, BUCKETS, build_aging
from app.auth import service as auth_service
from app.costing.fixed import is_inhouse, output_kg
from app.dispatch.stock import pending_qty
from app.extensions import db
from app.inventory.alerts import stock_alerts
from app.models import (ChartOfAccountsGroup, DeliveryChallan, FGMovement, GRN, Ledger, ProductionOutput, PurchaseInvoice, PurchaseOrder,
                        PurchaseReturn, Quotation, SalesInvoice, SalesReceipt, SalesReturn, StockMovement, Warehouse)
from app.payables.aging import build_payables
from app.production_orders.scheduler import live_schedule, today_ist

PERIODS = [("month", "This month"), ("7d", "7 days"), ("6m", "6 months"), ("fy", "This year")]
LATE_KEYS = ("b1", "b2", "b3", "b4")      # aging ke wo hisse jo due date paar kar chuke
# Chart ke rang (colour-blind safe jodi, dataviz validator se check): rang cheez ke saath chalta hai, number ke saath nahi
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
STOCK_TYPES = [("RM", "Raw material store"), ("QC_HOLD", "Waiting for QC"), ("WIP", "Work in progress"), ("FG", "Finished goods"),
               ("SCRAP", "Scrap"), ("TRANSIT", "In transit")]


# ---------- chhote helpers ----------

def rupees(value):
    # 30800.0 -> "₹ 30,800" ; minus -> "- ₹ 500"
    value = round(value or 0)
    return ("- " if value < 0 else "") + "₹ {:,.0f}".format(abs(value))


def compact(value):
    # Chart ke side ke number chhote: 1500 -> 1.5K, 250000 -> 2.5L, 12000000 -> 1.2Cr
    for size, suffix in ((1e7, "Cr"), (1e5, "L"), (1e3, "K")):
        if abs(value) >= size:
            return "{:g}{}".format(round(value / size, 1), suffix)
    return "{:g}".format(round(value, 1))


def _plural(count, word):
    return "%d %s%s" % (count, word, "" if count == 1 else "s")


def _month_add(day, months):
    # day ke mahine se `months` aage / peeche wale mahine ki 1 tareekh
    index = day.year * 12 + day.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def period_window(key, today):
    """(start, end, pichhle_start, pichhle_end, buckets[(label, from, to)]). Pichhla period utne hi din ka hota hai, taaki tulna sahi ho."""
    first = today.replace(day=1)
    buckets = []
    if key == "7d":
        start = today - timedelta(days=6)
        prev_start, prev_end = start - timedelta(days=7), start - timedelta(days=1)
        buckets = [((start + timedelta(days=i)).strftime("%d %b"), start + timedelta(days=i), start + timedelta(days=i)) for i in range(7)]
    elif key in ("6m", "fy"):
        if key == "6m":
            start = _month_add(first, -5)
            prev_start = _month_add(start, -6)
        else:
            start = date(today.year if today.month >= 4 else today.year - 1, 4, 1)     # Indian financial year: April se
            prev_start = date(start.year - 1, 4, 1)
        prev_end = min(prev_start + (today - start), start - timedelta(days=1))
        month = start
        while month <= today:
            buckets.append((month.strftime("%b"), month, min(_month_add(month, 1) - timedelta(days=1), today)))
            month = _month_add(month, 1)
    else:      # is mahine: hafte-hafte
        start = first
        prev_start = _month_add(first, -1)
        prev_end = min(prev_start + timedelta(days=today.day - 1), first - timedelta(days=1))
        day = start
        while day <= today:
            last = min(day + timedelta(days=6), today)
            label = day.strftime("%d %b") if day == last else "%d–%s" % (day.day, last.strftime("%d %b"))
            buckets.append((label, day, last))
            day = last + timedelta(days=1)
    return start, today, prev_start, prev_end, buckets


def _daily(model, date_column, value_column, start, end):
    # {tareekh: jod} sirf Posted aur delete na hue documents ka
    rows = (db.session.query(date_column, func.sum(value_column))
            .filter(model.is_deleted == False, model.status == "Posted", date_column >= start, date_column <= end)       # noqa: E712
            .group_by(date_column).all())
    return {day: float(total or 0) for day, total in rows}


def _total(daily, start, end):
    return sum(value for day, value in daily.items() if start <= day <= end)


def _minus(first, second):
    return {day: first.get(day, 0) - second.get(day, 0) for day in set(first) | set(second)}


def _delta(current, previous, up_is_good):
    # Pichhle period se farak. up_is_good None = na achha na bura (jaise purchase)
    if abs(previous) < 0.005:
        return {"text": "No earlier data to compare", "tone": "flat"}
    percent = (current - previous) / abs(previous) * 100
    if abs(percent) < 0.5:
        return {"text": "Same as the period before", "tone": "flat"}
    up = percent > 0
    tone = "flat" if up_is_good is None else ("good" if up == up_is_good else "bad")
    return {"text": "%s %.0f%% vs period before" % ("▲" if up else "▼", abs(percent)), "tone": tone}


def _spark(values, width=120, height=30):
    # SVG polyline ke points; saare zero ho to line nahi
    if len(values) < 2 or not any(abs(v) > 0.005 for v in values):
        return ""
    low, high = min(values + [0]), max(values + [0])
    span = (high - low) or 1
    step = width / (len(values) - 1)
    return " ".join("%.1f,%.1f" % (i * step, height - 2 - (v - low) / span * (height - 4)) for i, v in enumerate(values))


def _nice_top(value):
    # Axis ka upar wala saaf number (1, 2, 2.5, 5, 10 ke guna)
    if value <= 0:
        return 1
    size = 10 ** (len(str(int(value))) - 1) if value >= 1 else 1
    for factor in (1, 2, 2.5, 4, 5, 10):
        if value <= factor * size:
            return factor * size
    return 10 * size


def _chart(buckets, series, fmt):
    """Grouped column chart ka data. series = [(naam, rang, [value per bucket])]. Height % me (top = saaf number)."""
    biggest = max([max(values + [0]) for _n, _c, values in series] + [0])
    top = _nice_top(biggest)
    columns = []
    for index, (label, _start, _end) in enumerate(buckets):
        bars = [{"name": name, "color": color, "height": max(values[index], 0) / top * 100, "text": fmt(values[index])} for name, color, values in series]
        columns.append({"label": label, "bars": bars, "tip": label + " · " + " · ".join("%s %s" % (b["name"], b["text"]) for b in bars)})
    ticks = [{"pct": step * 25, "text": compact(top * step / 4)} for step in range(5)]
    return {"columns": columns, "ticks": ticks, "legend": [(name, color) for name, color, _v in series], "empty": biggest <= 0}


def _bars(items, limit=5):
    """Seedhi (horizontal) bar list: items = [(naam, value, text)] — sabse bada 100%."""
    items = [item for item in items if item[1] > 0.005][:limit]
    biggest = max([value for _n, value, _t in items] + [0]) or 1
    return [{"name": name, "text": text, "pct": value / biggest * 100} for name, value, text in items]


def _attention(level, tag, text, url, action):
    return {"level": level, "tag": tag, "text": text, "url": url, "action": action}


# ---------- panels ----------

def _money_series(can, start, end, prev_start, prev_end, buckets):
    """KPI cards + bada chart: net sales, collections, purchases, net profit."""
    kpis, series = [], []

    def add(label, daily, url, up_is_good, note, color=None, chart_name=None):
        values = [_total(daily, a, b) for _label, a, b in buckets]
        current, previous = _total(daily, start, end), _total(daily, prev_start, prev_end)
        kpis.append({"label": label, "value": rupees(current), "delta": _delta(current, previous, up_is_good), "note": note,
                     "spark": _spark(values), "url": url})
        if color:
            series.append((chart_name, color, values))

    if can("invoices"):
        sales = _minus(_daily(SalesInvoice, SalesInvoice.invoice_date, SalesInvoice.subtotal, prev_start, end),
                       _daily(SalesReturn, SalesReturn.return_date, SalesReturn.subtotal, prev_start, end))
        add("Net sales", sales, url_for("sales_invoices.invoices_list"), True, "Without GST, after returns", BLUE, "Sales")
    if can("receipts"):
        receipts = _daily(SalesReceipt, SalesReceipt.receipt_date, SalesReceipt.amount, prev_start, end)
        add("Collections", receipts, url_for("receipts.receipts_list"), True, "Money received from customers", AQUA, "Collections")
    if can("purchase_invoices"):
        bought = _minus(_daily(PurchaseInvoice, PurchaseInvoice.invoice_date, PurchaseInvoice.subtotal, prev_start, end),
                        _daily(PurchaseReturn, PurchaseReturn.return_date, PurchaseReturn.subtotal, prev_start, end))
        add("Purchases", bought, url_for("purchase_invoices.purchase_invoices_list"), None, "Without GST, after returns", ORANGE, "Purchases")
    if can("accounts_reports"):
        current = profit_loss(start, end)["net"] / 100
        previous = profit_loss(prev_start, prev_end)["net"] / 100
        values = [profit_loss(a, b)["net"] / 100 for _label, a, b in buckets]
        kpis.append({"label": "Net profit" if current >= 0 else "Net loss", "value": rupees(current), "delta": _delta(current, previous, True),
                     "note": "As booked in accounts", "spark": _spark(values), "url": url_for("reports.profit_loss")})
    chart = _chart(buckets, series, rupees) if series else None
    return kpis, chart


def _cash_panel(today):
    balances = movements(None, today)
    rows, total = [], 0
    for group in ChartOfAccountsGroup.query.filter(ChartOfAccountsGroup.name.in_(["Cash-in-hand", "Bank Accounts"])).all():
        for ledger in Ledger.query.filter_by(group_id=group.id).order_by(Ledger.name).all():
            value = balances.get(ledger.id, 0) / 100
            total += value
            rows.append({"name": ledger.name, "text": rupees(value), "negative": value < 0})
    return {"total": rupees(total), "negative": total < 0, "rows": rows, "url": url_for("reports.cashbook")}


def _party_panel(rows, totals, url, word):
    overdue = sum(totals[key] for key in LATE_KEYS)
    # "other" = bina bill wala hissa (opening balance). Ise bar me dikhana zaroori hai, warna bars ka jod total se match nahi karta
    parts = [(BUCKET_LABELS[key], totals[key]) for key in BUCKETS] + [("Opening / other balance", totals["other"])]
    buckets = _bars([(name, value, rupees(value)) for name, value in parts], limit=len(parts))
    top = sorted([r for r in rows if r["net"] > 0.005], key=lambda r: -r["net"])
    return {"total": rupees(totals["net"]), "overdue": rupees(overdue) if overdue > 0.005 else "", "count": _plural(len(top), word),
            "advance": rupees(totals["advance"]) if totals["advance"] > 0.005 else "",
            "buckets": buckets, "top": [{"name": r["name"], "text": rupees(r["net"])} for r in top[:3]], "url": url}


def _overdue_items(rows, tag, url, action):
    items = []
    for row in rows:
        late = [line for line in row["lines"] if line["late"] > 0 and line["outstanding"] > 0.005]
        if late:
            amount = sum(line["outstanding"] for line in late)
            items.append(_attention("bad", tag, "%s: %s, %s late" % (row["name"], rupees(amount), _plural(max(line["late"] for line in late), "day")), url, action))
    return items[:3]


def _output_panel(start, end, buckets):
    # Bikne wale maal ka output KG me (in-house flux jaisa maal isme nahi): good aur scrap
    outputs = ProductionOutput.query.filter(ProductionOutput.is_deleted == False, ProductionOutput.status == "Posted",                # noqa: E712
                                            ProductionOutput.output_date >= start, ProductionOutput.output_date <= end).all()
    outputs = [o for o in outputs if not is_inhouse(o)]

    def scrap_kg(output):
        order = output.production_order
        return (output.scrap_qty or 0) * (order.unit_weight if order and order.unit_weight else 1)

    good = [sum(output_kg(o) for o in outputs if a <= o.output_date <= b) for _label, a, b in buckets]
    scrap = [sum(scrap_kg(o) for o in outputs if a <= o.output_date <= b) for _label, a, b in buckets]
    total_good, total_scrap = sum(good), sum(scrap)
    rate = total_scrap / (total_good + total_scrap) * 100 if total_good + total_scrap > 0 else None
    return {"chart": _chart(buckets, [("Good", BLUE, good), ("Scrap", ORANGE, scrap)], lambda v: "{:,.1f} KG".format(v)),
            "good": "{:,.1f} KG".format(total_good), "scrap_rate": "%.1f%%" % rate if rate is not None else "—",
            "url": url_for("production_output.production_output_list")}


def _machine_panel():
    from app.dashboard.routes import machine_board          # routes.py is file ko import karta hai, isliye yahan andar
    total = machine_board()["total"]
    parts = [("Running", total["running"] - total["held"], BLUE), ("On hold", total["held"], "#eda100"),
             ("Free", total["free"], "#1F9D6A"), ("Unavailable", total["inactive"], "#d03b3b")]
    count = sum(value for _n, value, _c in parts)
    return {"total": total["machines"], "busy": total["running"], "down": total["down"],
            "use": "%.0f%%" % (total["running"] / total["machines"] * 100) if total["machines"] else "—",
            "parts": [{"name": n, "value": v, "color": c, "pct": v / count * 100 if count else 0} for n, v, c in parts],
            "url": url_for("dashboard.dashboard_page", tab="board")}


def _orders_panel(today):
    from app.production_orders.routes import progress_info
    ordered, _materials, schedule = live_schedule(today)
    open_orders = [o for o in ordered if o.status in ("Draft", "Released", "In production")]
    progress, stage_now = progress_info(ordered, schedule, today)
    rows, late = [], []
    for order in open_orders:
        plan = schedule.get(order.id)
        planned_end = plan["end"] if plan else None
        is_late = bool(order.needed_by_date and planned_end and planned_end > order.needed_by_date)
        stage = stage_now.get(order.id)
        rows.append({"no": order.prod_no, "product": order.product.name if order.product else "", "status": order.status,
                     "stage": "%s (%d of %d)" % (stage["name"] or "Done", stage["done"], stage["total"]) if stage else "Not started",
                     "pct": progress.get(order.id, 0), "end": planned_end.strftime("%d %b") if planned_end else "—",
                     "needed": order.needed_by_date.strftime("%d %b") if order.needed_by_date else "—", "late": is_late})
        if is_late:
            late.append(_attention("bad", "Late order", "%s needed by %s, planned to finish %s" % (
                order.prod_no, order.needed_by_date.strftime("%d %b"), planned_end.strftime("%d %b")),
                url_for("production_orders.production_orders_list"), "Open orders"))
    rows.sort(key=lambda r: (not r["late"], r["status"] != "In production"))
    panel = {"rows": rows[:6], "total": len(rows), "late": len(late), "working": len([r for r in rows if r["status"] == "In production"]),
             "url": url_for("production_orders.production_orders_list")}
    return panel, late[:3]


def _pipeline_panel():
    # Sales ka safar: har padaav par kitne document aur kitne ke (GST ke bina)
    def quote_value(quotations):
        return sum(line.net_value for q in quotations for line in q.lines)

    quotes = Quotation.query.filter(Quotation.is_deleted == False).all()                                                               # noqa: E712
    open_quotes = [q for q in quotes if q.status in ("Draft", "Sent")]
    approved = [q for q in quotes if q.status == "Approved"]
    to_send = [q for q in quotes if q.status == "Ordered" and any(pending_qty(line) > 0 for line in q.lines)]
    pending_value = sum((line.net_value / line.qty if line.qty else 0) * pending_qty(line) for q in to_send for line in q.lines)
    challans = DeliveryChallan.query.filter(DeliveryChallan.is_deleted == False, DeliveryChallan.status == "Dispatched",               # noqa: E712
                                            DeliveryChallan.invoice_id.is_(None)).all()
    challan_value = sum(row.qty * (row.quotation_line.net_value / row.quotation_line.qty if row.quotation_line.qty else 0) for c in challans for row in c.lines)
    unpaid = [i for i in SalesInvoice.query.filter(SalesInvoice.is_deleted == False, SalesInvoice.status == "Posted").all()           # noqa: E712
              if i.outstanding > 0.005]
    steps = [("Open quotations", len(open_quotes), quote_value(open_quotes), "quotations.quotations_list"),
             ("Approved, to confirm", len(approved), quote_value(approved), "quotations.quotations_list"),
             ("Orders to dispatch", len(to_send), pending_value, "dispatch.dispatch_list"),
             ("Dispatched, to invoice", len(challans), challan_value, "sales_invoices.invoices_list"),
             ("Invoices not paid", len(unpaid), sum(i.outstanding for i in unpaid), "sales_invoices.invoices_list")]
    return [{"name": n, "count": c, "value": rupees(v), "endpoint": e} for n, c, v, e in steps]


def _top_lists(start, end):
    invoices = SalesInvoice.query.filter(SalesInvoice.is_deleted == False, SalesInvoice.status == "Posted",                           # noqa: E712
                                         SalesInvoice.invoice_date >= start, SalesInvoice.invoice_date <= end).all()
    customers, products = {}, {}
    for invoice in invoices:
        name = invoice.quotation.customer.name
        customers[name] = customers.get(name, 0) + (invoice.subtotal or 0)
        for line in invoice.lines:
            product = line.product.name if line.product else "—"
            products[product] = products.get(product, 0) + line.net_value

    def ranked(values):
        return _bars([(n, v, rupees(v)) for n, v in sorted(values.items(), key=lambda kv: -kv[1])])

    return ranked(customers), ranked(products)


def _stock_panel():
    values = dict(db.session.query(Warehouse.warehouse_type, func.sum(StockMovement.value))
                  .join(Warehouse, Warehouse.id == StockMovement.warehouse_id).group_by(Warehouse.warehouse_type).all())
    values["FG"] = (values.get("FG") or 0) + (db.session.query(func.sum(FGMovement.value)).scalar() or 0)
    items = [(label, float(values.get(key) or 0), rupees(values.get(key) or 0)) for key, label in STOCK_TYPES]
    return {"total": rupees(sum(v for _l, v, _t in items)), "bars": _bars(items, limit=len(items)), "url": url_for("inventory.stock_valuation")}


# ---------- main ----------

def build_overview(user, period="month"):
    """Dashboard ka poora data. Jis panel ki permission nahi, uski value None rehti hai (template use banata hi nahi)."""
    def can(key):
        return auth_service.user_can(user, key)

    if period not in dict(PERIODS):
        period = "month"
    today = today_ist()
    start, end, prev_start, prev_end, buckets = period_window(period, today)
    attention = []
    data = {"today": today, "period": period, "periods": PERIODS, "start": start, "end": end, "prev_start": prev_start, "prev_end": prev_end}
    data["kpis"], data["chart"] = _money_series(can, start, end, prev_start, prev_end, buckets)
    data["cash"] = _cash_panel(today) if can("accounts_reports") else None

    data["receivable"] = data["payable"] = None
    if can("receivables"):
        rows, totals = build_aging(today)
        url = url_for("aging.receivables_aging")
        data["receivable"] = _party_panel(rows, totals, url, "customer")
        attention += _overdue_items(rows, "Customer overdue", url, "Open receivables")
    if can("payables"):
        rows, totals = build_payables(today)
        url = url_for("payables.payables_aging")
        data["payable"] = _party_panel(rows, totals, url, "vendor")
        attention += _overdue_items(rows, "Vendor payment due", url, "Open payables")

    data["output"] = _output_panel(start, end, buckets) if can("production_output") else None
    data["machines"] = _machine_panel() if can("dashboard") else None
    if data["machines"] and data["machines"]["down"]:
        attention.append(_attention("warn", "Machine", "%s unavailable (breakdown, maintenance or off)" % _plural(data["machines"]["down"], "machine"),
                                    data["machines"]["url"], "Open machine board"))
    data["orders"] = None
    if can("production_orders"):
        data["orders"], late = _orders_panel(today)
        attention += late

    data["pipeline"] = None
    if can("quotations"):
        data["pipeline"] = _pipeline_panel()
        for step in data["pipeline"]:
            step["url"] = url_for(step["endpoint"])
    data["top_customers"] = data["top_products"] = None
    if can("invoices"):
        data["top_customers"], data["top_products"] = _top_lists(start, end)
        waiting = SalesInvoice.query.filter(SalesInvoice.is_deleted == False, SalesInvoice.status == "Waiting approval").count()      # noqa: E712
        if waiting:
            attention.append(_attention("warn", "Approval", "%s below cost waiting for approval" % _plural(waiting, "invoice"),
                                        url_for("sales_invoices.invoices_list"), "Open invoices"))

    data["stock"] = _stock_panel() if can("valuation") else None
    data["reorder"] = None
    if can("stock"):
        low = [row for row in stock_alerts()["rows"] if row["status"] != "over"]
        data["reorder"] = {"total": len(low), "url": url_for("inventory.stock_list"),
                           "rows": [{"name": r["material"].name, "have": "{:g} {}".format(r["available"], r["unit"]),
                                     "level": "{:g}".format(r["minimum"] or r["reorder"] or 0), "coming": "{:g}".format(r["on_order"]),
                                     "status": r["label"], "out": r["status"] == "out"} for r in low[:6]]}
        if low:
            attention.append(_attention("warn", "Stock", "%s at or below reorder level" % _plural(len(low), "material"),
                                        url_for("inventory.stock_list"), "Open stock"))

    data["purchasing"] = None
    rows = []
    if can("purchase_orders"):
        pos = PurchaseOrder.query.filter(PurchaseOrder.is_deleted == False, PurchaseOrder.status.in_(["Open", "Partial"])).all()      # noqa: E712
        value = sum(line.remaining_qty * line.rate for po in pos for line in po.lines if line.remaining_qty > 0)
        rows.append({"name": "Purchase orders still to arrive", "value": str(len(pos)), "note": rupees(value) + " without GST",
                     "url": url_for("purchase_orders.purchase_orders_list")})
    if can("inward_qc"):
        from app.inward_qc.routes import final_qc_line_ids
        done = final_qc_line_ids()
        grns = GRN.query.filter(GRN.status.in_(["Pending QC", "Partial QC"]), GRN.is_deleted == False).all()                          # noqa: E712
        pending = sum(1 for grn in grns for line in grn.lines if line.id not in done)
        rows.append({"name": "Material lots waiting for QC", "value": str(pending), "note": "Inward inspection pending" if pending else "Nothing waiting",
                     "url": url_for("inward_qc.inward_qc_list")})
        if pending:
            attention.append(_attention("warn", "QC pending", "%s waiting for inspection" % _plural(pending, "material lot"),
                                        url_for("inward_qc.inward_qc_list"), "Open inward QC"))
    if rows:
        data["purchasing"] = rows

    attention.sort(key=lambda item: 0 if item["level"] == "bad" else 1)      # laal pehle
    data["attention"] = attention
    return data
