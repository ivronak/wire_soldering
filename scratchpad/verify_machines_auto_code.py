import _guard  # Safety: asli erp.db pe chalti hai — bina ERP_ALLOW_DB_SCRIPTS=1 ke ruk jaayegi (dekho _guard.py)
# Machines auto-code verify (test data cleaned up at end)
# Kya check karta hai:
#   1) /machines page load + disabled auto-code input (value = next_code)
#   2) Add form ka "code" ignore hota hai -> route khud MC-XXXX banata hai
#   3) Add ke baad next_code +1 badhta hai
#   4) Edit pe code immutable rehta hai, name/capacity badal jaate hain
import sys
from app import app
from app.models import Machines, WorkStage
from app.machines.routes import generate_next_machine_code
from app.extensions import db

client = app.test_client()
results = []


def check(label, cond, extra=""):
    results.append((label, bool(cond)))
    print(f"[{'PASS' if cond else 'FAIL'}] {label}" + (f"  -> {extra}" if extra else ""))


TEST_NAME = "Zz Test Machine Auto"
TEST_NAME2 = "Zz Test Machine Auto Renamed"

# 0) pehle se bacha hua test data (agar pichli baar crash hua ho) hata do
with app.app_context():
    for m in Machines.query.filter(Machines.name.in_([TEST_NAME, TEST_NAME2])).all():
        db.session.delete(m)
    db.session.commit()

# ek valid work_stage chahiye add ke liye
with app.app_context():
    stage = WorkStage.query.filter_by(is_deleted=False).first()
    stage_id = stage.id if stage else None
check("A Work Stage exists for FK", stage_id is not None, f"stage_id={stage_id}")

# 1) list page load + disabled auto-code input
resp = client.get("/machines")
html = resp.get_data(as_text=True)
check("GET /machines returns 200", resp.status_code == 200, f"status={resp.status_code}")

with app.app_context():
    expected_next = generate_next_machine_code()

check(
    'List page shows disabled code input with next_code value',
    (f'name="code" value="{expected_next}" disabled' in html),
    f"expected_next={expected_next}",
)

# 2) add with a bogus code -> route must ignore form code
resp = client.post(
    "/machines/add",
    data={"code": "HACK99", "name": TEST_NAME, "work_stage_id": str(stage_id), "capacity": "111 units/hr"},
    follow_redirects=False,
)
check("POST /machines/add redirects (302)", resp.status_code in (302, 303), f"status={resp.status_code}")

created_id = None
with app.app_context():
    m = Machines.query.filter_by(name=TEST_NAME).first()
    created_id = m.id if m else None
    check("Machine created in DB", m is not None)
    if m:
        check("Auto code used (bogus 'HACK99' ignored)", m.code == expected_next, f"code={m.code}")
        check("capacity saved", m.capacity == "111 units/hr", f"capacity={m.capacity}")
        check("work_stage_id saved", m.work_stage_id == stage_id, f"work_stage_id={m.work_stage_id}")

# 3) next code increments by 1
with app.app_context():
    after = generate_next_machine_code()
serial = int(expected_next.split("-")[1])
exp_after = f"MC-{serial + 1:04d}"
check("Next code increments after add", after == exp_after, f"after={after} expected={exp_after}")

# 4) edit -> code immutable, name/capacity update
if created_id:
    resp = client.post(
        f"/machines/edit/{created_id}",
        data={"code": "HACKED", "name": TEST_NAME2, "work_stage_id": str(stage_id), "capacity": "999 units/hr"},
        follow_redirects=False,
    )
    check("POST /machines/edit redirects (302)", resp.status_code in (302, 303), f"status={resp.status_code}")

    with app.app_context():
        m = Machines.query.get(created_id)
        check("Edit kept code immutable", m.code == expected_next, f"code={m.code}")
        check("Edit updated name", m.name == TEST_NAME2, f"name={m.name}")
        check("Edit updated capacity", m.capacity == "999 units/hr", f"capacity={m.capacity}")

# 5) cleanup
with app.app_context():
    if created_id:
        m = Machines.query.get(created_id)
        if m:
            db.session.delete(m)
            db.session.commit()
        check("Cleanup: test machine removed", Machines.query.get(created_id) is None)

passed = sum(1 for _, ok in results if ok)
total = len(results)
print(f"\nTOTAL: {passed}/{total} passed")
sys.exit(0 if passed == total else 1)
