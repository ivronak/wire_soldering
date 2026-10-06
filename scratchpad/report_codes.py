# Current master codes ka snapshot — renumber se pehle
from app import app
from app.models import (WorkStage, Machines, RmCategories, RawMaterial,
                        ProductCategories, Warehouse, Vendor, Customer)

TARGETS = [
    ("WorkStage", WorkStage),
    ("Machines", Machines),
    ("RmCategories", RmCategories),
    ("RawMaterial", RawMaterial),
    ("ProductCategories", ProductCategories),
    ("Warehouse", Warehouse),
    ("Vendor", Vendor),
    ("Customer", Customer),
]

with app.app_context():
    for label, model in TARGETS:
        rows = model.query.order_by(model.id.asc()).all()
        print(f"\n=== {label} ({len(rows)} rows) ===")
        for r in rows:
            name = getattr(r, "name", "")
            print(f"  id={r.id:<4} code={r.code!r:<12} name={name!r}")
