# Ye Units module ka Blueprint hai - Unit Master ke saare routes (URLs) yahan honge.
# Abhi sirf 3 kaam: list dikhao, add karo, soft-toggle (is_active).
# Search / Edit / filter baad me sikh ke add karenge.
from flask import Blueprint, render_template, request, redirect, url_for
from app.models import Unit
from app.extensions import db
from sqlalchemy import or_

units_bp = Blueprint("units", __name__, template_folder="templates")


@units_bp.route("/units")
def units_list():
    # Agar table khaali hai to pehli baar 3 demo units daal do
    if Unit.query.count() == 0:
        db.session.add(Unit(code="KG", name="Kilogram", is_base_unit=True))
        db.session.add(Unit(code="GM", name="Gram", is_base_unit=True))
        db.session.add(Unit(code="PCS", name="Piece", is_base_unit=False))
        db.session.commit()  # bina commit ke DB me save nahi hota
    
    q = (request.args.get("q") or "").strip()
    status = (request.args.get("status") or "all").strip().lower()

    query = Unit.query
    query = query.filter(Unit.is_deleted == False)

    if q:
        # code YA name me yeh text ho (case-insensitive)
        like = f"%{q}%"
        query = query.filter(
            or_(
                Unit.code.ilike(like),
                Unit.name.ilike(like),
            )
        )
    
    if status == "active":
        query = query.filter(Unit.is_active == True)
    elif status == "inactive":
        query = query.filter(Unit.is_active == False)

    # List database se
    units = query.order_by(Unit.code).all()
    all_units = Unit.query.filter(Unit.is_deleted == False).all()
    total_count = len(all_units)
    active_count = sum(1 for u in all_units if u.is_active)
    inactive_count = total_count - active_count
    result_count = len(units)

    return render_template(
        "units.html",
        units=units,
        active_nav="units",
        q=q,
        total_count=total_count,
        active_count=active_count,
        inactive_count=inactive_count,
        result_count=result_count,
        status=status,
    )


@units_bp.route("/units/add", methods=["POST"])
def units_add():
    # Form se values nikalo (.strip = aage-peeche spaces hatao)
    code = (request.form.get("code") or "").strip().upper()
    name = (request.form.get("name") or "").strip()
    # Checkbox tick ho to "1" aata hai; nahi to None
    is_base = request.form.get("is_base_unit") == "1"

    if not code or not name:
        # Abhi simple: wapas list pe bhej do
        return redirect(url_for("units.units_list"))

    # Duplicate code? (unique column — warna DB error)
    existing = Unit.query.filter_by(code=code).first()
    if existing:
        if existing.is_deleted:
            existing.is_deleted = False
            existing.name = name
            existing.is_base_unit = is_base
            existing.is_active = True
            db.session.commit()
            return redirect(url_for("units.units_list"))
        return redirect(url_for("units.units_list"))

    db.session.add(Unit(
        code=code,
        name=name,
        is_base_unit=is_base,
        is_active=True,
        is_deleted=False,
    ))
    db.session.commit()

    return redirect(url_for("units.units_list"))


@units_bp.route("/units/toggle/<int:unit_id>", methods=["POST"])
def units_toggle(unit_id):
    # <int:unit_id> = URL se number, jaise /units/toggle/2 → unit_id=2
    unit = Unit.query.get_or_404(unit_id)
    # True tha to False, False tha to True
    unit.is_active = not unit.is_active
    db.session.commit()
    q = request.form.get("q") or ""
    status = request.form.get("status") or "all"
    return redirect(url_for("units.units_list", q=q or None, status=status))

@units_bp.route("/units/edit/<int:unit_id>", methods=["POST"])
def units_edit(unit_id):
    # URL se unit; nahi mila to 404
    unit = Unit.query.get_or_404(unit_id)

    code = (request.form.get("code") or "").strip().upper()
    name = (request.form.get("name") or "").strip()
    is_base = request.form.get("is_base_unit") == "1"
    q = (request.form.get("q") or "").strip()
    status = (request.form.get("status") or "all").strip().lower()

    if not code or not name:
        return redirect(url_for("units.units_list", q=q or None, status=status))

    # Dusri row pe same code? (apni id chhod ke)
    dup = Unit.query.filter(Unit.code == code, Unit.id != unit_id).first()
    if dup:
        return redirect(url_for("units.units_list", q=q or None, status=status))    

    unit.code = code
    unit.name = name
    unit.is_base_unit = is_base
    db.session.commit()

    return redirect(url_for("units.units_list", q=q or None, status=status)) 

@units_bp.route("/units/delete/<int:unit_id>", methods=["POST"])
def units_delete(unit_id):
    unit = Unit.query.get_or_404(unit_id)    
    # Soft-delete - hard delete nahi; list filter is_deleted se hide karega
    unit.is_deleted = True
    db.session.commit()

    q = (request.form.get("q") or "").strip()
    status = (request.form.get("status") or "all").strip().lower()
    return redirect(url_for("units.units_list", q=q or None, status=status))