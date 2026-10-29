# Production Line master (Line 1, Line 2 ...): ek line = 8 stages ka poora set + apni machines + apni daily capacity (KG/din).
# Client change #1 (2026-10-26). Machine ek hi line me (machines.line_id). Order ko line dena agle step me aayega.
from flask import Blueprint, render_template, redirect, url_for, request, flash

from app.extensions import db
from app.models import ProductionLine, Machines

production_lines_bp = Blueprint("production_lines", __name__, template_folder="templates")


def generate_next_line_code():
    # Auto-serial (LN-0001 ...) — form se code nahi aata
    last = ProductionLine.query.order_by(ProductionLine.id.desc()).first()
    return f"LN-{(last.id + 1) if last else 1:04d}"


def read_form():
    # (values, error). Naam aur daily capacity (KG/din) zaroori; handler (line ka incharge) optional.
    name = (request.form.get("name") or "").strip()
    capacity = request.form.get("daily_capacity_kg", type=float)
    handler = (request.form.get("handler") or "").strip() or None
    if not name:
        return None, "Line name is required."
    if capacity is None or capacity <= 0:
        return None, "Daily capacity (KG per day) must be more than 0."
    return {"name": name, "capacity": capacity, "handler": handler}, None


@production_lines_bp.route("/production_lines")
def production_lines_list():
    lines = ProductionLine.query.filter_by(is_deleted=False).order_by(ProductionLine.code).all()
    return render_template("production_lines.html", lines=lines, next_code=generate_next_line_code(),
                           total_count=len(lines), result_count=len(lines), active_nav="production_lines")


@production_lines_bp.route("/production_lines/add", methods=["POST"])
def production_lines_add():
    values, error = read_form()
    if error:
        flash(error, "error")
        return redirect(url_for("production_lines.production_lines_list"))
    db.session.add(ProductionLine(code=generate_next_line_code(), name=values["name"], daily_capacity_kg=values["capacity"],
                                  handler=values["handler"], is_active=True, is_deleted=False))
    db.session.commit()
    flash("Production line saved.", "success")
    return redirect(url_for("production_lines.production_lines_list"))


@production_lines_bp.route("/production_lines/edit/<int:line_id>", methods=["POST"])
def production_lines_edit(line_id):
    line = ProductionLine.query.filter_by(id=line_id, is_deleted=False).first_or_404()
    values, error = read_form()
    if error:
        flash(error, "error")
        return redirect(url_for("production_lines.production_lines_list"))
    line.name, line.daily_capacity_kg, line.handler = values["name"], values["capacity"], values["handler"]
    db.session.commit()
    flash("Production line updated.", "success")
    return redirect(url_for("production_lines.production_lines_list"))


@production_lines_bp.route("/production_lines/toggle/<int:line_id>", methods=["POST"])
def production_lines_toggle(line_id):
    line = ProductionLine.query.filter_by(id=line_id, is_deleted=False).first_or_404()
    line.is_active = not line.is_active
    db.session.commit()
    flash(f"{line.name} is now {'in use' if line.is_active else 'stopped'}.", "success")
    return redirect(url_for("production_lines.production_lines_list"))


@production_lines_bp.route("/production_lines/delete/<int:line_id>", methods=["POST"])
def production_lines_delete(line_id):
    # Soft delete (business data hard delete nahi). Machines abhi is line me hon to rokte hain — pehle unhe doosri line me do.
    line = ProductionLine.query.filter_by(id=line_id, is_deleted=False).first_or_404()
    if line.active_machines:
        flash(f"{line.name} still has {len(line.active_machines)} machine(s). Move them to another line first.", "error")
        return redirect(url_for("production_lines.production_lines_list"))
    line.is_deleted = True
    db.session.commit()
    flash("Production line removed from the list (kept in database).", "success")
    return redirect(url_for("production_lines.production_lines_list"))
