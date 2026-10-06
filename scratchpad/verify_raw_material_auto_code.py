import _guard  # Safety: asli erp.db pe chalti hai — bina ERP_ALLOW_DB_SCRIPTS=1 ke ruk jaayegi (dekho _guard.py)
# Raw Material auto-code verify (test data cleaned up at end)
#   1) /raw_materials page load + disabled auto-code input (value = next_code)
#   2) Add form ka "code" ignore hota hai -> route khud RM-XXXX banata hai
#   3) Add ke baad next_code +1 badhta hai
#   4) Edit pe code immutable, name/description update
import sys
from app import app
from app.models import RawMaterial, RmCategories, Unit
from app.raw_materials.routes import generate_next_raw_material_code
from app.extensions import db

client = app.test_client()
results = []


def check(label, cond, extra=""):
    results.append((label, bool(cond)))
    print(f"[{'PASS' if cond else 'FAIL'}] {label}" + (f"  -> {extra}" if extra else ""))


TEST_NAME = "Zz Test RM Auto"
TEST_NAME2 = "Zz Test RM Auto Renamed"

with app.app_context():
    for m in RawMaterial.query.filter(RawMaterial.name.in_([TEST_NAME, TEST_NAME2])).all():
        db.session.delete(m)
    db.session.commit()

    # FK ke liye existing category + unit (agar na mile to verify ruk jayega)
    cat = RmCategories.query.filter(RmCategories.is_deleted == False).first()
    unit = Unit.query.first()
    cat_id = cat.id if cat else None
    unit_id = unit.id if unit else None

check("Found a category for FK", cat_id is not None, f"cat_id={cat_id}")
check("Found a unit for FK", unit_id is not None, f"unit_id={unit_id}")

resp = client.get("/raw_materials")
html = resp.get_data(as_text=True)
check("GET /raw_materials returns 200", resp.status_code == 200, f"status={resp.status_code}")

with app.app_context():
    expected_next = generate_next_raw_material_code()

check(
    'List page shows disabled code input with next_code value',
    (f'name="code" value="{expected_next}" disabled' in html),
    f"expected_next={expected_next}",
)

resp = client.post(
    "/raw_materials/add",
    data={
        "code": "HACK99",
        "name": TEST_NAME,
        "description": "temp desc",
        "category_id": cat_id,
        "base_unit_id": unit_id,
    },
    follow_redirects=False,
)
check("POST /raw_materials/add redirects (302)", resp.status_code in (302, 303), f"status={resp.status_code}")

created_id = None
with app.app_context():
    m = RawMaterial.query.filter_by(name=TEST_NAME).first()
    created_id = m.id if m else None
    check("Raw Material created in DB", m is not None)
    if m:
        check("Auto code used (bogus 'HACK99' ignored)", m.code == expected_next, f"code={m.code}")
        check("description saved", m.description == "temp desc", f"description={m.description}")

with app.app_context():
    after = generate_next_raw_material_code()
serial = int(expected_next.split("-")[1])
exp_after = f"RM-{serial + 1:04d}"
check("Next code increments after add", after == exp_after, f"after={after} expected={exp_after}")

if created_id:
    resp = client.post(
        f"/raw_materials/edit/{created_id}",
        data={
            "code": "HACKED",
            "name": TEST_NAME2,
            "description": "changed desc",
            "category_id": cat_id,
            "base_unit_id": unit_id,
        },
        follow_redirects=False,
    )
    check("POST /raw_materials/edit redirects (302)", resp.status_code in (302, 303), f"status={resp.status_code}")

    with app.app_context():
        m = RawMaterial.query.get(created_id)
        check("Edit kept code immutable", m.code == expected_next, f"code={m.code}")
        check("Edit updated name", m.name == TEST_NAME2, f"name={m.name}")
        check("Edit updated description", m.description == "changed desc", f"description={m.description}")

with app.app_context():
    if created_id:
        m = RawMaterial.query.get(created_id)
        if m:
            db.session.delete(m)
            db.session.commit()
        check("Cleanup: test material removed", RawMaterial.query.get(created_id) is None)

passed = sum(1 for _, ok in results if ok)
total = len(results)
print(f"\nTOTAL: {passed}/{total} passed")
sys.exit(0 if passed == total else 1)
