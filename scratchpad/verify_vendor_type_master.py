import _guard  # Safety: asli erp.db pe chalti hai — bina ERP_ALLOW_DB_SCRIPTS=1 ke ruk jaayegi (dekho _guard.py)
# Step 0 verify - Vendor Type Master: table + seed + CRUD + page smoke
# (test data cleaned up at the end)
from app import app
from app.models import VendorType
from app.extensions import db
from sqlalchemy import inspect

client = app.test_client()
results = []


def check(label, cond, extra=""):
    results.append(("PASS" if cond else "FAIL", label, extra))


EXPECTED_NAMES = [
    "Raw Material Supplier",
    "Job Worker / Sub-contractor",
    "Transporter",
    "Service Provider",
    "Other",
]

# --- 1. Schema + seed -------------------------------------------------------
with app.app_context():
    insp = inspect(db.engine)
    check("vendor_types table exists", insp.has_table("vendor_types"))

    rows = VendorType.query.order_by(VendorType.id).all()
    check("5 rows seeded", len(rows) == 5, f"got {len(rows)}")
    check("codes VT-0001..VT-0005",
          [r.code for r in rows] == [f"VT-{i:04d}" for i in range(1, 6)],
          str([r.code for r in rows]))
    check("names = old dropdown options",
          [r.name for r in rows] == EXPECTED_NAMES,
          str([r.name for r in rows]))
    check("all seeded active + not deleted",
          all(r.is_active and not r.is_deleted for r in rows))

# --- 2. Page smoke ----------------------------------------------------------
r = client.get("/vendor_types")
check("GET /vendor_types -> 200", r.status_code == 200, str(r.status_code))
check("page shows a seeded name", "Raw Material Supplier" in r.get_data(as_text=True))

# --- 3. Add -----------------------------------------------------------------
r = client.post("/vendor_types/add", data={"name": "ZZ Test Type"})
check("add redirects", r.status_code in (301, 302), str(r.status_code))

with app.app_context():
    t = VendorType.query.filter_by(name="ZZ Test Type").first()
    check("added row exists", t is not None)
    tid = t.id if t else None
    check("auto code = VT-0006", bool(t) and t.code == "VT-0006", t.code if t else "")

# --- 4. Edit ----------------------------------------------------------------
if tid:
    client.post(f"/vendor_types/edit/{tid}", data={"name": "ZZ Test Type Renamed"})
    with app.app_context():
        t = VendorType.query.get(tid)
        check("edit applied", t.name == "ZZ Test Type Renamed", t.name)

# --- 5. Toggle --------------------------------------------------------------
    client.post(f"/vendor_types/toggle/{tid}")
    with app.app_context():
        t = VendorType.query.get(tid)
        check("toggle -> stopped", t.is_active is False, str(t.is_active))

# --- 6. Soft delete ---------------------------------------------------------
    client.post(f"/vendor_types/delete/{tid}")
    with app.app_context():
        t = VendorType.query.get(tid)
        check("soft delete flag set", t.is_deleted is True, str(t.is_deleted))
        # cleanup - test row ko DB se hata do
        db.session.delete(t)
        db.session.commit()

    with app.app_context():
        check("cleanup done", VendorType.query.get(tid) is None)

# --- Report -----------------------------------------------------------------
for status, label, extra in results:
    print(f"{status} :: {label}" + (f"  [{extra}]" if extra else ""))

passed = sum(1 for s, _, _ in results if s == "PASS")
print(f"\nTOTAL: {passed}/{len(results)} PASS")
