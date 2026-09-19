# Ye Units module ka Blueprint hai - Unit Master ke saare routes (URLs) yahan honge 
from flask import Blueprint, render_template

units_bp = Blueprint("units", __name__, template_folder="templates")

# abhi database nahi bana - isliye fake (hardcoded) list.
# Baad me (F5/F6) yeh list database se aayegi, yahan se hat jayegi.

UNITS=[
    {"code": "KG", "name": "Kilogram"},
    {"code": "GM", "name": "Gram"},
    {"code": "PCS", "name": "Piece"},
]

@units_bp.route("/units")
def units_list():
    return render_template("units.html", units=UNITS)