import _guard  # Safety: asli erp.db pe chalti hai — bina ERP_ALLOW_DB_SCRIPTS=1 ke ruk jaayegi (dekho _guard.py)
# Work Stages auto-code verify (test data cleaned up at end)
# Kya check karta hai:
#   1) /work_stages page load + disabled auto-code input (value = next_code)
#   2) Add form ka "code" ignore hota hai -> route khud WS-XXXX banata hai
#   3) Add ke baad next_code +1 badhta hai
#   4) Edit pe code immutable rehta hai, name/sort badal jaate hain
import sys
from app import app
from app.models import WorkStage
from app.work_stages.routes import generate_next_work_stage_code
from app.extensions import db

client = app.test_client()
results = []


def check(label, cond, extra=""):
    results.append((label, bool(cond)))
    print(f"[{'PASS' if cond else 'FAIL'}] {label}" + (f"  -> {extra}" if extra else ""))


TEST_NAME = "Zz Test Work Stage"
TEST_NAME2 = "Zz Test Work Stage Renamed"

# 0) pehle se bacha hua test data (agar pichli baar crash hua ho) hata do
with app.app_context():
    for s in WorkStage.query.filter(WorkStage.name.in_([TEST_NAME, TEST_NAME2])).all():
        db.session.delete(s)
    db.session.commit()

# 1) list page load + disabled auto-code input
resp = client.get("/work_stages")
html = resp.get_data(as_text=True)
check("GET /work_stages returns 200", resp.status_code == 200, f"status={resp.status_code}")

with app.app_context():
    expected_next = generate_next_work_stage_code()

check(
    'List page shows disabled code input with next_code value',
    (f'name="code" value="{expected_next}" disabled' in html),
    f"expected_next={expected_next}",
)

# 2) add with a bogus code -> route must ignore form code
resp = client.post(
    "/work_stages/add",
    data={"code": "HACK99", "name": TEST_NAME, "sort_order": "55"},
    follow_redirects=False,
)
check("POST /work_stages/add redirects (302)", resp.status_code in (302, 303), f"status={resp.status_code}")

created_id = None
with app.app_context():
    s = WorkStage.query.filter_by(name=TEST_NAME).first()
    created_id = s.id if s else None
    check("Work Stage created in DB", s is not None)
    if s:
        check("Auto code used (bogus 'HACK99' ignored)", s.code == expected_next, f"code={s.code}")
        check("sort_order saved", s.sort_order == 55, f"sort_order={s.sort_order}")

# 3) next code increments by 1
with app.app_context():
    after = generate_next_work_stage_code()
serial = int(expected_next.split("-")[1])
exp_after = f"WS-{serial + 1:04d}"
check("Next code increments after add", after == exp_after, f"after={after} expected={exp_after}")

# 4) edit -> code immutable, name/sort update
if created_id:
    resp = client.post(
        f"/work_stages/edit/{created_id}",
        data={"code": "HACKED", "name": TEST_NAME2, "sort_order": "77"},
        follow_redirects=False,
    )
    check("POST /work_stages/edit redirects (302)", resp.status_code in (302, 303), f"status={resp.status_code}")

    with app.app_context():
        s = WorkStage.query.get(created_id)
        check("Edit kept code immutable", s.code == expected_next, f"code={s.code}")
        check("Edit updated name", s.name == TEST_NAME2, f"name={s.name}")
        check("Edit updated sort_order", s.sort_order == 77, f"sort_order={s.sort_order}")

# 5) cleanup
with app.app_context():
    if created_id:
        s = WorkStage.query.get(created_id)
        if s:
            db.session.delete(s)
            db.session.commit()
        check("Cleanup: test stage removed", WorkStage.query.get(created_id) is None)

passed = sum(1 for _, ok in results if ok)
total = len(results)
print(f"\nTOTAL: {passed}/{total} passed")
sys.exit(0 if passed == total else 1)
