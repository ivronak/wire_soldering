# Sales S10 — Profit report: har Posted invoice par kitne me bika, kitna kharcha laga (material + fixed), kitna profit.
# Judta hai: sales_invoices (bikri), delivery_challan_lines (kaunse batch se gaya), fg_batches / production_outputs (batch ki poori cost),
#            sales_returns (wapas aaya maal: bikri ghatti, achha maal wapas to uski cost bhi wapas).
#
# Rules (memory.md S10 decision):
#   * Bikri = invoice ki items ki value discount ke baad, GST ke bina. Invoice ke charges (shipping...) bhi bikri me jodte hain (net: Add - Minus).
#   * Cost = jo maal gaya uski batch cost: Material (batch ka material cost) + Fixed (output ka fixed overhead per unit, jaisa app/costing/full_cost.py).
#     Cost "abhi ki" hai: mahina Final hone par fixed rate badal sakta hai (Approx -> Final), isliye profit bhi usi hisaab se update hota hai.
#   * Credit note (Sales return): bikri me se us maal ki value ghatti. Achha maal (good) stock me wapas gaya => uski cost bhi ghatti.
#     Kharab (damaged) maal ki cost nahi ghatti => wo nuksan profit me dikhta hai.
#   * Sirf Posted invoice (Waiting approval / Cancelled nahi). Owner ke liye report — roles aane par Owner-only hogi.
from app.costing.full_cost import batch_full_cost
from app.models import Quotation, SalesInvoice


def _unit_costs(challan_line):
    # (material per unit, fixed per unit) us batch ke
    material = challan_line.unit_cost or 0
    full = batch_full_cost(challan_line.batch)
    fixed = max(round(full - (challan_line.batch.unit_cost or 0), 4), 0)
    return material, fixed


def invoice_profit(invoice):
    """Ek invoice ka hisaab: {"lines": [...], totals...}. Sab rupee me, 2 decimal."""
    challan_lines = [cl for challan in invoice.challans if challan.status == "Dispatched" for cl in challan.lines]
    returns = [r for r in invoice.returns if r.status == "Posted" and not r.is_deleted]
    lines = []
    for il in invoice.lines:
        mine = {cl.id: cl for cl in challan_lines if cl.quotation_line_id == il.quotation_line_id}
        material = fixed = 0.0
        for cl in mine.values():
            m_u, f_u = _unit_costs(cl)
            material += cl.qty * m_u
            fixed += cl.qty * f_u
        sold_value = il.net_value
        ret_value = ret_qty = back_material = back_fixed = 0.0
        for rt in returns:
            for g in rt.groups:
                if g["invoice_line"].id == il.id:
                    ret_value += g["net"]
                    ret_qty += g["qty"]
            for row in rt.lines:
                if row.invoice_line_id == il.id and row.challan_line_id in mine and row.good_qty:
                    m_u, f_u = _unit_costs(mine[row.challan_line_id])
                    back_material += row.good_qty * m_u
                    back_fixed += row.good_qty * f_u
        net_revenue = sold_value - ret_value
        material_cost = material - back_material
        fixed_cost = fixed - back_fixed
        profit = net_revenue - material_cost - fixed_cost
        lines.append({"product": il.product.name, "code": il.product.code, "qty": il.qty, "returned": round(ret_qty, 4), "rate": il.net_unit_price,
                      "sold": round(sold_value, 2), "returns": round(ret_value, 2), "revenue": round(net_revenue, 2),
                      "material": round(material_cost, 2), "fixed": round(fixed_cost, 2), "cost": round(material_cost + fixed_cost, 2), "profit": round(profit, 2)})
    charges = round(invoice.charges_total or 0, 2)
    revenue = round(sum(l["revenue"] for l in lines) + charges, 2)
    material = round(sum(l["material"] for l in lines), 2)
    fixed = round(sum(l["fixed"] for l in lines), 2)
    profit = round(revenue - material - fixed, 2)
    return {"invoice": invoice, "lines": lines, "sold_items": round(sum(l["sold"] for l in lines), 2), "returns": round(sum(l["returns"] for l in lines), 2),
            "charges": charges, "revenue": revenue, "material": material, "fixed": fixed, "cost": round(material + fixed, 2), "profit": profit,
            "margin": round(profit / revenue * 100, 1) if revenue > 0.004 else None}


def build_profit(date_from, date_to, customer_id=None):
    """Period ke Posted invoices ka profit: (rows, totals)."""
    query = (SalesInvoice.query.join(Quotation, Quotation.id == SalesInvoice.quotation_id)
             .filter(SalesInvoice.status == "Posted", SalesInvoice.is_deleted == False, SalesInvoice.invoice_date >= date_from, SalesInvoice.invoice_date <= date_to))
    if customer_id:
        query = query.filter(Quotation.customer_id == customer_id)
    rows = [invoice_profit(inv) for inv in query.order_by(SalesInvoice.invoice_date, SalesInvoice.id).all()]
    totals = {key: round(sum(r[key] for r in rows), 2) for key in ("sold_items", "returns", "charges", "revenue", "material", "fixed", "cost", "profit")}
    totals["margin"] = round(totals["profit"] / totals["revenue"] * 100, 1) if totals["revenue"] > 0.004 else None
    return rows, totals
