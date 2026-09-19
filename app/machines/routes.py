from flask import Blueprint, render_template, redirect, url_for, request
from app.models import Machines
from app.extensions import db
from datetime import date


machines_bp = Blueprint("machines",__name__, template_folder="templates")

@machines_bp.route("/machines")
def machines_list():
    if Machines.query.count() == 0:
        db.session.add(Machines(code = "MC-CUT-01", name = "Cutting Bench", work_center = "Cutting", capacity = "500 units/hr", installed_date = date(2026, 9, 19), status = "active",))
        db.session.commit()

    machines = (
        Machines.query.filter(Machines.is_deleted == False).order_by(Machines.code).all()
    )

    total_count = len(machines)

    return render_template(
        "machines.html",
        machines=machines,
        total_count=total_count,
        active_nav="machines",
        result_count=total_count,
    )