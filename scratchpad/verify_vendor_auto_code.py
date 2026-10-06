import _guard  # Safety: asli erp.db pe chalti hai — bina ERP_ALLOW_DB_SCRIPTS=1 ke ruk jaayegi (dekho _guard.py)
# Vendor auto-code verify (test data cleaned up at end)
#   1) /vendors page load + disabled auto-code input (value = next_code)
#   2) Add form ka "code" ignore hota hai -> route khud V-XXXX banata hai
#   3) Add ke baad next_code +1 badhta hai
#   4) Edit pe code immutable, name update
import sys
from app import app
from app.models import Vendor, State, Ledger
from app.vendors.routes import generate_next_vendor_code
from app.extensions import db

client = app.test_client()
results = []


def check(label, cond, extra=""):
    results.append((label, bool(cond)))
    print(f"[{'PASS' if cond else 'FAIL'}] {label}" + (f"  -> {extra}" if extra else ""))


TEST_NAME = "Zz Test Vendor Auto"
TEST_NAME2 = "Zz Test Vendor Auto Renamed"
TEMP_STATE = "Zz Test State Vendor"

temp_state_id = None


def cleanup_test_vendors():
    for v in Vendor.query.filter(Vendor.name.in_([TEST_NAME, TEST_NAME2])).all():
        led_id = v.ledger_id
        db.session.delete(v)
        db.session.commit()
        led = Ledger.query.get(led_id) if led_id else None
        if led:
            db.session.delete(led)
            db.session.commit()


with app.app_context():
    cleanup_test_vendors()

    state = State.query.filter(State.is_deleted == False).first()
    if state is None:
        state = State(code="ZZV", name=TEMP_STATE, gst_state_code="99",
                      is_active=True, is_deleted=False)
        db.session.add(state)
        db.session.commit()
        temp_state_id = state.id
    state_id = state.id

check("Found a state for FK", state_id is not None, f"state_id={state_id}")

resp = client.get("/vendors")
html = resp.get_data(as_text=True)
check("GET /vendors returns 200", resp.status_code == 200, f"status={resp.status_code}")

with app.app_context():
    expected_next = generate_next_vendor_code()

check(
    'List page shows disabled code input with next_code value',
    (f'name="code" value="{expected_next}" disabled' in html),
    f"expected_next={expected_next}",
)

resp = client.post(
    "/vendors/add",
    data={"code": "HACK99", "name": TEST_NAME, "state_id": state_id, "opening_balance": "0"},
    follow_redirects=False,
)
check("POST /vendors/add redirects (302)", resp.status_code in (302, 303), f"status={resp.status_code}")

created_id = None
with app.app_context():
    v = Vendor.query.filter_by(name=TEST_NAME).first()
    created_id = v.id if v else None
    check("Vendor created in DB", v is not None)
    if v:
        check("Auto code used (bogus 'HACK99' ignored)", v.code == expected_next, f"code={v.code}")
        check("Ledger created + linked", v.ledger_id is not None, f"ledger_id={v.ledger_id}")

with app.app_context():
    after = generate_next_vendor_code()
serial = int(expected_next.split("-")[1])
exp_after = f"V-{serial + 1:04d}"
check("Next code increments after add", after == exp_after, f"after={after} expected={exp_after}")

if created_id:
    resp = client.post(
        f"/vendors/edit/{created_id}",
        data={"code": "HACKED", "name": TEST_NAME2, "state_id": state_id, "opening_balance": "0"},
        follow_redirects=False,
    )
    check("POST /vendors/edit redirects (302)", resp.status_code in (302, 303), f"status={resp.status_code}")

    with app.app_context():
        v = Vendor.query.get(created_id)
        check("Edit kept code immutable", v.code == expected_next, f"code={v.code}")
        check("Edit updated name", v.name == TEST_NAME2, f"name={v.name}")

with app.app_context():
    cleanup_test_vendors()
    check("Cleanup: test vendor removed", Vendor.query.filter(Vendor.name.in_([TEST_NAME, TEST_NAME2])).first() is None)

    if temp_state_id:
        s = State.query.get(temp_state_id)
        if s:
            db.session.delete(s)
            db.session.commit()

passed = sum(1 for _, ok in results if ok)
total = len(results)
print(f"\nTOTAL: {passed}/{total} passed")
sys.exit(0 if passed == total else 1)
