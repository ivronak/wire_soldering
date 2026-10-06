import _guard  # Safety: asli erp.db pe chalti hai — bina ERP_ALLOW_DB_SCRIPTS=1 ke ruk jaayegi (dekho _guard.py)
# Existing master data ke codes ko naye auto format me badlo.
#   Generator ka pattern: {PREFIX}-{id:04d}   (next = max_id + 1)
#   Isliye har row ka naya code = f"{prefix}-{row.id:04d}"
#   Two-phase: pehle TEMP unique codes, phir final — unique-collision se bachne ke liye.
from app import app
from app.models import (WorkStage, Machines, RmCategories, RawMaterial,
                        ProductCategories, Warehouse, Vendor, Customer)
from app.extensions import db

TARGETS = [
    (WorkStage, "WS"),
    (Machines, "MC"),
    (RmCategories, "RMC"),
    (RawMaterial, "RM"),
    (ProductCategories, "PC"),
    (Warehouse, "WH"),
    (Vendor, "V"),
    (Customer, "C"),
]

with app.app_context():
    for model, prefix in TARGETS:
        rows = model.query.order_by(model.id.asc()).all()
        print(f"\n=== {model.__name__} -> {prefix}- ( {len(rows)} rows ) ===")

        # Phase 1: sabhi codes ko TEMP unique value do (kisi se collide na kare)
        for r in rows:
            print(f"  id={r.id:<4} {r.code!r}  ->  {prefix}-{r.id:04d}")
            r.code = f"TMP-{prefix}-{r.id}"
        db.session.flush()

        # Phase 2: ab final canonical codes
        for r in rows:
            r.code = f"{prefix}-{r.id:04d}"
        db.session.commit()

    print("\nRenumber complete.")
