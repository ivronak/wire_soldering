import _guard  # Safety: asli erp.db pe chalti hai — bina ERP_ALLOW_DB_SCRIPTS=1 ke ruk jaayegi (dekho _guard.py)
# RM Categories auto-code verify (test data cleaned up at end)
#   1) /rm_categories page load + disabled auto-code input (value = next_code)
#   2) Add form ka "code" ignore hota hai -> route khud RMC-XXXX banata hai
#   3) Add ke baad next_code +1 badhta hai
#   4) Edit pe code immutable, name/description update
import sys
from app import app
from app.models import RmCategories
from app.rm_categories.routes import generate_next_rm_category_code
from app.extensions import db

client = app.test_client()
results = []


def check(label, cond, extra=""):
    results.append((label, bool(cond)))
    print(f"[{'PASS' if cond else 'FAIL'}] {label}" + (f"  -> {extra}" if extra else ""))


TEST_NAME = "Zz Test RmCat Auto"
TEST_NAME2 = "Zz Test RmCat Auto Renamed"

with app.app_context():
    for c in RmCategories.query.filter(RmCategories.name.in_([TEST_NAME, TEST_NAME2])).all():
        db.session.delete(c)
    db.session.commit()

resp = client.get("/rm_categories")
html = resp.get_data(as_text=True)
check("GET /rm_categories returns 200", resp.status_code == 200, f"status={resp.status_code}")

with app.app_context():
    expected_next = generate_next_rm_category_code()

check(
    'List page shows disabled code input with next_code value',
    (f'name="code" value="{expected_next}" disabled' in html),
    f"expected_next={expected_next}",
)

resp = client.post(
    "/rm_categories/add",
    data={"code": "HACK99", "name": TEST_NAME, "description": "temp desc"},
    follow_redirects=False,
)
check("POST /rm_categories/add redirects (302)", resp.status_code in (302, 303), f"status={resp.status_code}")

created_id = None
with app.app_context():
    c = RmCategories.query.filter_by(name=TEST_NAME).first()
    created_id = c.id if c else None
    check("RM Category created in DB", c is not None)
    if c:
        check("Auto code used (bogus 'HACK99' ignored)", c.code == expected_next, f"code={c.code}")
        check("description saved", c.description == "temp desc", f"description={c.description}")

with app.app_context():
    after = generate_next_rm_category_code()
serial = int(expected_next.split("-")[1])
exp_after = f"RMC-{serial + 1:04d}"
check("Next code increments after add", after == exp_after, f"after={after} expected={exp_after}")

if created_id:
    resp = client.post(
        f"/rm_categories/edit/{created_id}",
        data={"code": "HACKED", "name": TEST_NAME2, "description": "changed desc"},
        follow_redirects=False,
    )
    check("POST /rm_categories/edit redirects (302)", resp.status_code in (302, 303), f"status={resp.status_code}")

    with app.app_context():
        c = RmCategories.query.get(created_id)
        check("Edit kept code immutable", c.code == expected_next, f"code={c.code}")
        check("Edit updated name", c.name == TEST_NAME2, f"name={c.name}")
        check("Edit updated description", c.description == "changed desc", f"description={c.description}")

with app.app_context():
    if created_id:
        c = RmCategories.query.get(created_id)
        if c:
            db.session.delete(c)
            db.session.commit()
        check("Cleanup: test category removed", RmCategories.query.get(created_id) is None)

passed = sum(1 for _, ok in results if ok)
total = len(results)
print(f"\nTOTAL: {passed}/{total} passed")
sys.exit(0 if passed == total else 1)
