import _guard  # Safety: asli erp.db pe chalti hai — bina ERP_ALLOW_DB_SCRIPTS=1 ke ruk jaayegi (dekho _guard.py)
# Warehouse auto-code verify (test data cleaned up at end)
#   1) /warehouses page load + disabled auto-code input (value = next_code)
#   2) Add form ka "code" ignore hota hai -> route khud WH-XXXX banata hai
#   3) Add ke baad next_code +1 badhta hai
#   4) Edit pe code immutable, name/type/location update
import sys
from app import app
from app.models import Warehouse, Branch, State
from app.warehouses.routes import generate_next_warehouse_code
from app.extensions import db

client = app.test_client()
results = []


def check(label, cond, extra=""):
    results.append((label, bool(cond)))
    print(f"[{'PASS' if cond else 'FAIL'}] {label}" + (f"  -> {extra}" if extra else ""))


TEST_NAME = "Zz Test WH Auto"
TEST_NAME2 = "Zz Test WH Auto Renamed"
TEMP_BRANCH = "Zz Test Branch WH"

temp_branch_id = None
temp_state_id = None

with app.app_context():
    for w in Warehouse.query.filter(Warehouse.name.in_([TEST_NAME, TEST_NAME2])).all():
        db.session.delete(w)
    db.session.commit()

    branch = Branch.query.filter(Branch.is_deleted == False).first()
    if branch is None:
        state = State.query.first()
        if state is None:
            state = State(code="ZZWH", name="Zz Test State WH", gst_state_code="99",
                          is_active=True, is_deleted=False)
            db.session.add(state)
            db.session.commit()
            temp_state_id = state.id
        branch = Branch(name=TEMP_BRANCH, state_id=state.id, is_active=True, is_deleted=False)
        db.session.add(branch)
        db.session.commit()
        temp_branch_id = branch.id
    branch_id = branch.id

check("Found a branch for FK", branch_id is not None, f"branch_id={branch_id}")

resp = client.get("/warehouses")
html = resp.get_data(as_text=True)
check("GET /warehouses returns 200", resp.status_code == 200, f"status={resp.status_code}")

with app.app_context():
    expected_next = generate_next_warehouse_code()

check(
    'List page shows disabled code input with next_code value',
    (f'name="code" value="{expected_next}" disabled' in html),
    f"expected_next={expected_next}",
)

resp = client.post(
    "/warehouses/add",
    data={
        "code": "HACK99",
        "name": TEST_NAME,
        "warehouse_type": "rm",
        "branch_id": branch_id,
        "location": "Rack A1",
    },
    follow_redirects=False,
)
check("POST /warehouses/add redirects (302)", resp.status_code in (302, 303), f"status={resp.status_code}")

created_id = None
with app.app_context():
    w = Warehouse.query.filter_by(name=TEST_NAME).first()
    created_id = w.id if w else None
    check("Warehouse created in DB", w is not None)
    if w:
        check("Auto code used (bogus 'HACK99' ignored)", w.code == expected_next, f"code={w.code}")
        check("warehouse_type saved", w.warehouse_type == "rm", f"type={w.warehouse_type}")
        check("location saved", w.location == "Rack A1", f"location={w.location}")

with app.app_context():
    after = generate_next_warehouse_code()
serial = int(expected_next.split("-")[1])
exp_after = f"WH-{serial + 1:04d}"
check("Next code increments after add", after == exp_after, f"after={after} expected={exp_after}")

if created_id:
    resp = client.post(
        f"/warehouses/edit/{created_id}",
        data={
            "code": "HACKED",
            "name": TEST_NAME2,
            "warehouse_type": "fg",
            "branch_id": branch_id,
            "location": "Rack B2",
        },
        follow_redirects=False,
    )
    check("POST /warehouses/edit redirects (302)", resp.status_code in (302, 303), f"status={resp.status_code}")

    with app.app_context():
        w = Warehouse.query.get(created_id)
        check("Edit kept code immutable", w.code == expected_next, f"code={w.code}")
        check("Edit updated name", w.name == TEST_NAME2, f"name={w.name}")
        check("Edit updated warehouse_type", w.warehouse_type == "fg", f"type={w.warehouse_type}")
        check("Edit updated location", w.location == "Rack B2", f"location={w.location}")

with app.app_context():
    if created_id:
        w = Warehouse.query.get(created_id)
        if w:
            db.session.delete(w)
            db.session.commit()
        check("Cleanup: test warehouse removed", Warehouse.query.get(created_id) is None)

    # temp branch/state cleanup (sirf jab humne banaya ho)
    if temp_branch_id:
        b = Branch.query.get(temp_branch_id)
        if b:
            db.session.delete(b)
            db.session.commit()
    if temp_state_id:
        s = State.query.get(temp_state_id)
        if s:
            db.session.delete(s)
            db.session.commit()

passed = sum(1 for _, ok in results if ok)
total = len(results)
print(f"\nTOTAL: {passed}/{total} passed")
sys.exit(0 if passed == total else 1)
