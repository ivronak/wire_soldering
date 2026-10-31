# Rack master: warehouse ke andar ke racks (A, B, C ...). Sirf naam + warehouse; GRN / FG receipt par rack chunna agle steps me aayega.
# Delete nahi hota, sirf is_deleted = True (soft) — CLAUDE.md rule 2.
from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import Rack, Warehouse

racks_bp = Blueprint("racks", __name__, template_folder="templates")


def generate_next_rack_code():
    # RK-0001, RK-0002 ... (sabse bade number + 1, taaki delete ke baad bhi code repeat na ho)
    numbers = [int(r[0].split("-")[1]) for r in db.session.query(Rack.code).all() if r[0].startswith("RK-") and r[0].split("-")[1].isdigit()]
    return f"RK-{(max(numbers) if numbers else 0) + 1:04d}"


def _warehouse_from_form():
    warehouse_id = request.form.get("warehouse_id", type=int)
    warehouse = db.session.get(Warehouse, warehouse_id) if warehouse_id else None
    if warehouse is None or warehouse.is_deleted or not warehouse.is_active:
        return None
    return warehouse


def _is_duplicate(warehouse_id, name, skip_id=None):
    query = Rack.query.filter(Rack.is_deleted == False, Rack.warehouse_id == warehouse_id, db.func.lower(Rack.name) == name.lower())
    if skip_id:
        query = query.filter(Rack.id != skip_id)
    return query.first() is not None


@racks_bp.route("/racks")
def racks_list():
    racks = Rack.query.filter(Rack.is_deleted == False).order_by(Rack.warehouse_id, Rack.name).all()
    warehouses = Warehouse.query.filter_by(is_deleted=False, is_active=True).order_by(Warehouse.name).all()
    return render_template("racks.html", active_nav="racks", racks=racks, warehouses=warehouses, next_code=generate_next_rack_code(),
                           total_count=len(racks), result_count=len(racks))


@racks_bp.route("/racks/add", methods=["POST"])
def racks_add():
    name = (request.form.get("name") or "").strip()[:40]
    warehouse = _warehouse_from_form()
    if not name:
        flash("Enter the rack name.", "error")
    elif warehouse is None:
        flash("Choose the warehouse this rack belongs to.", "error")
    elif _is_duplicate(warehouse.id, name):
        flash(f"{warehouse.name} already has a rack named {name}.", "error")
    else:
        db.session.add(Rack(code=generate_next_rack_code(), name=name, warehouse_id=warehouse.id, is_active=True, is_deleted=False))
        db.session.commit()
        flash("Rack saved.", "success")
    return redirect(url_for("racks.racks_list"))


@racks_bp.route("/racks/edit/<int:rack_id>", methods=["POST"])
def racks_edit(rack_id):
    rack = Rack.query.filter_by(id=rack_id, is_deleted=False).first_or_404()
    name = (request.form.get("name") or "").strip()[:40]
    warehouse = _warehouse_from_form()
    if not name:
        flash("Enter the rack name.", "error")
    elif warehouse is None:
        flash("Choose the warehouse this rack belongs to.", "error")
    elif _is_duplicate(warehouse.id, name, skip_id=rack.id):
        flash(f"{warehouse.name} already has a rack named {name}.", "error")
    else:
        rack.name = name
        rack.warehouse_id = warehouse.id
        db.session.commit()
        flash("Rack updated.", "success")
    return redirect(url_for("racks.racks_list"))


@racks_bp.route("/racks/toggle/<int:rack_id>", methods=["POST"])
def racks_toggle(rack_id):
    rack = Rack.query.filter_by(id=rack_id, is_deleted=False).first_or_404()
    rack.is_active = not rack.is_active
    db.session.commit()
    return redirect(url_for("racks.racks_list"))


@racks_bp.route("/racks/delete/<int:rack_id>", methods=["POST"])
def racks_delete(rack_id):
    rack = Rack.query.filter_by(id=rack_id, is_deleted=False).first_or_404()
    rack.is_deleted = True
    db.session.commit()
    flash("Rack removed from the list (kept in database).", "success")
    return redirect(url_for("racks.racks_list"))
