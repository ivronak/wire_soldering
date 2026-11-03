# Material plan page: agle 30 din ka material hisaab (kya kam padega, PO kab tak dalna hai). Hisaab app/material_plan/plan.py me.
# Yahan page + "Create draft PO": kami wale materials se ek vendor ka ek Draft PO (kai orders ka maal ek PO me).
from datetime import date, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.material_plan.plan import HORIZON_DAYS, draft_po_by_material, last_po_lines, material_plan
from app.models import PurchaseOrder, PurchaseOrderLine, RawMaterial, Vendor

material_plan_bp = Blueprint("material_plan", __name__, template_folder="templates")


@material_plan_bp.route("/material_plan")
def material_plan_page():
    view = request.args.get("view", "short")
    if view not in ("short", "all"):
        view = "short"
    plan = material_plan()
    # "short" = jinme kami hai, jinke PO ki date nahi likhi, ya jo date nikal chuke (overdue) PO ke bharose covered hain; "all" = 30 din ke saare materials
    rows = [r for r in plan["rows"] if view == "all" or r["short_date"] or r["undated"] > 0 or r["overdue"]]
    return render_template("material_plan.html", active_nav="material_plan", plan=plan, rows=rows, view=view, horizon=HORIZON_DAYS)


@material_plan_bp.route("/material_plan/create_po", methods=["POST"])
def material_plan_create_po():
    # Ek vendor ka Draft PO. Rate / tax / unit supplier ki pichli PO line se (form ke bharose nahi); qty form se (badal sakte hain, 0 = hata do).
    # PO Draft me banta hai: Purchase orders page par rate dekh ke vendor ka bill laga ke confirm karna hai.
    back = redirect(url_for("material_plan.material_plan_page"))
    vendor = db.session.get(Vendor, request.form.get("vendor_id", type=int) or 0)
    if vendor is None or vendor.is_deleted or not vendor.is_active:
        flash("Choose an active vendor for the purchase order.", "error")
        return back
    last = last_po_lines()
    drafts = draft_po_by_material()
    picked = []                 # [(material, qty, po_line)]
    seen = set()
    index = 0
    while request.form.get(f"material_id_{index}"):
        material = db.session.get(RawMaterial, request.form.get(f"material_id_{index}", type=int) or 0)
        qty_raw = (request.form.get(f"qty_{index}") or "").strip()
        index += 1
        if material is None or material.is_deleted:
            flash("A material in the list is not valid.", "error")
            return back
        if material.id in seen:
            flash(f"{material.name} is listed twice. Keep one line.", "error")
            return back
        seen.add(material.id)
        if not qty_raw:
            continue
        try:
            qty = float(qty_raw)
        except ValueError:
            flash(f"Quantity of {material.name} is not a number.", "error")
            return back
        if qty < 0:
            flash(f"Quantity of {material.name} cannot be negative.", "error")
            return back
        if qty == 0:
            continue
        found = last.get(material.id)
        if found is None or found[0].vendor_id != vendor.id:
            flash(f"{material.name} is no longer bought from {vendor.name}. Reload the page.", "error")
            return back
        if material.id in drafts:
            flash(f"{material.name} is already in draft {drafts[material.id]}. Open that PO instead of raising another.", "error")
            return back
        picked.append((material, round(qty, 4), found[1]))
    if not picked:
        flash("Enter a quantity for at least one material.", "error")
        return back

    today = date.today()
    plan = material_plan(today)
    orders = sorted({o for r in plan["rows"] if r["material"].id in {m.id for m, _q, _l in picked} for o in r["orders"]})
    warehouse = picked[0][2].po.warehouse
    year = today.year
    count = PurchaseOrder.query.filter(PurchaseOrder.po_no.like(f"PO-{year}-%")).count()
    po = PurchaseOrder(po_no=f"PO-{year}-{count + 1:03d}", vendor_id=vendor.id, warehouse_id=warehouse.id, po_date=today,
                       expected_delivery_date=today + timedelta(days=vendor.lead_time_days) if vendor.lead_time_days is not None else None,
                       status="Draft", remarks=("Raised from Material plan for " + ", ".join(orders))[:255], payment_terms_id=vendor.payment_terms_id, is_deleted=False)
    db.session.add(po)
    db.session.flush()
    for material, qty, source in picked:
        db.session.add(PurchaseOrderLine(po_id=po.id, raw_material_id=material.id, ordered_qty=qty, unit_id=source.unit_id,
                                         tax_rate_id=source.tax_rate_id, rate=source.rate, discount_percent=0))
    db.session.commit()
    flash(f"Draft {po.po_no} created for {vendor.name} with {len(picked)} material{'' if len(picked) == 1 else 's'}. "
          "Open it on the Purchase orders page, check the rates, add the vendor's bill and confirm.", "success")
    return back
