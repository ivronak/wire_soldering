# Opening stock: software shuru hone se pehle jo maal store me pada hai use ledger me daalna (ek baar ka kaam, warehouse-wise).
# Draft -> Post (stock ledger me OPENING rows, har line ka naya lot) -> Cancel (sirf jab maal chheda na gaya ho).
# Stock kab / kitna badalta hai: sirf app/inventory/posting.py (post_opening / cancel_opening).
from datetime import date, datetime

from flask import render_template, Blueprint, request, redirect, url_for, flash

from app.extensions import db
from app.inventory.posting import post_opening, cancel_opening, InventoryError
from app.models import OpeningStock, OpeningStockLine, RawMaterial, Warehouse

opening_stock_bp = Blueprint("opening_stock", __name__, template_folder="templates")


def list_url(tab="pending"):
    return url_for("opening_stock.opening_stock_list", tab=tab)


@opening_stock_bp.route("/opening_stock")
def opening_stock_list():
    tab = (request.args.get("tab") or "pending").strip().lower()
    if tab != "completed":
        tab = "pending"
    base = OpeningStock.query.filter(OpeningStock.is_deleted == False)
    pending = base.filter(OpeningStock.status == "Draft").order_by(OpeningStock.id.desc()).all()
    completed = base.filter(OpeningStock.status.in_(["Posted", "Cancelled"])).order_by(OpeningStock.id.desc()).all()
    materials = RawMaterial.query.filter(RawMaterial.is_deleted == False, RawMaterial.is_active == True).order_by(RawMaterial.name).all()
    return render_template(
        "opening_stock.html", active_nav="opening_stock", tab=tab,
        sheets=pending if tab == "pending" else completed, pending_count=len(pending), completed_count=len(completed),
        warehouses=Warehouse.query.filter(Warehouse.is_deleted == False, Warehouse.is_active == True, Warehouse.warehouse_type == "RM").order_by(Warehouse.name).all(),
        material_options=[{"id": m.id, "label": f"{m.code} — {m.name}", "unit": m.base_unit.code if m.base_unit else ""} for m in materials],
        today=date.today().isoformat(),
    )


def read_opening_form():
    warehouse_id = request.form.get("warehouse_id", type=int)
    warehouse = db.session.get(Warehouse, warehouse_id) if warehouse_id else None
    if warehouse is None or warehouse.is_deleted or not warehouse.is_active or warehouse.warehouse_type != "RM":
        return None, "Choose an active store (raw material) warehouse."
    try:
        as_of = datetime.strptime((request.form.get("as_of_date") or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        return None, "Enter the date the stock is counted as of."
    if as_of > date.today():
        return None, "The opening stock date cannot be in the future."

    lines = []
    i = 0
    while True:
        material_id = request.form.get(f"material_id_{i}", type=int)
        if material_id is None:
            break
        qty = request.form.get(f"qty_{i}", type=float)
        cost = request.form.get(f"cost_{i}", type=float)
        batch = (request.form.get(f"batch_{i}") or "").strip()[:30]
        i += 1
        if qty is None or qty == 0:
            continue
        material = db.session.get(RawMaterial, material_id)
        if material is None or material.is_deleted or not material.is_active:
            return None, "A selected material was not found."
        if qty < 0:
            return None, f"{material.name}: quantity cannot be negative."
        if cost is None or cost < 0:
            return None, f"{material.name}: enter the cost per {material.base_unit.code if material.base_unit else 'unit'} (0 if unknown)."
        lines.append((material, round(qty, 4), round(cost, 4), batch))
    if not lines:
        return None, "Enter a quantity for at least one material."
    return {"warehouse": warehouse, "as_of": as_of, "lines": lines, "remarks": (request.form.get("remarks") or "").strip()[:255]}, None


@opening_stock_bp.route("/opening_stock/add", methods=["POST"])
def opening_stock_add():
    data, error = read_opening_form()
    if error:
        flash(error, "error")
        return redirect(list_url("pending"))
    year = data["as_of"].year
    count = OpeningStock.query.filter(OpeningStock.opening_no.like(f"OS-{year}-%")).count()
    sheet = OpeningStock(opening_no=f"OS-{year}-{count + 1:03d}", as_of_date=data["as_of"], warehouse=data["warehouse"],
                         status="Draft", remarks=data["remarks"] or None, is_deleted=False)
    db.session.add(sheet)
    for material, qty, cost, batch in data["lines"]:
        db.session.add(OpeningStockLine(opening=sheet, raw_material=material, qty=qty, unit_cost=cost, batch_no=batch or None))
    if (request.form.get("opening_action") or "draft").strip() == "post":
        try:
            post_opening(sheet)
        except InventoryError as stock_error:
            db.session.rollback()
            flash(str(stock_error), "error")
            return redirect(list_url("pending"))
        sheet.status = "Posted"
    db.session.commit()
    if sheet.status == "Posted":
        flash(f"{sheet.opening_no} posted: the opening stock is now in {data['warehouse'].name}.", "success")
        return redirect(list_url("completed"))
    flash(f"{sheet.opening_no} saved as Draft. Post it to put the stock in.", "success")
    return redirect(list_url("pending"))


@opening_stock_bp.route("/opening_stock/post/<int:sheet_id>", methods=["POST"])
def opening_stock_post(sheet_id):
    sheet = OpeningStock.query.filter_by(id=sheet_id, is_deleted=False).first_or_404()
    if sheet.status != "Draft":
        flash("Only a draft can be posted.", "error")
        return redirect(list_url("completed"))
    try:
        post_opening(sheet)
    except InventoryError as stock_error:
        db.session.rollback()
        flash(str(stock_error), "error")
        return redirect(list_url("pending"))
    sheet.status = "Posted"
    db.session.commit()
    flash(f"{sheet.opening_no} posted: the opening stock is now in {sheet.warehouse.name}.", "success")
    return redirect(list_url("completed"))


@opening_stock_bp.route("/opening_stock/cancel/<int:sheet_id>", methods=["POST"])
def opening_stock_cancel(sheet_id):
    sheet = OpeningStock.query.filter_by(id=sheet_id, is_deleted=False).first_or_404()
    if sheet.status == "Cancelled":
        flash("Already cancelled.", "error")
        return redirect(list_url("completed"))
    was_posted = sheet.status == "Posted"
    if was_posted:
        try:
            cancel_opening(sheet)
        except InventoryError as stock_error:
            db.session.rollback()
            flash(str(stock_error), "error")
            return redirect(list_url("completed"))
    sheet.status = "Cancelled"
    db.session.commit()
    flash(f"{sheet.opening_no} cancelled." + (" The stock was taken out again." if was_posted else ""), "success")
    return redirect(list_url("pending" if not was_posted else "completed"))
