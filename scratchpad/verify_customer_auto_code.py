import _guard  # Safety: asli erp.db pe chalti hai — bina ERP_ALLOW_DB_SCRIPTS=1 ke ruk jaayegi (dekho _guard.py)
# Customer auto-code verify (test data cleaned up at end)
#   1) /customers page load + disabled auto-code input (value = next_code)
#   2) Add form ka "code" ignore hota hai -> route khud C-XXXX banata hai
#   3) Add ke baad next_code +1 badhta hai
#   4) Edit pe code immutable, name update
import sys
from app import app
from app.models import Customer, State, Ledger
from app.customers.routes import generate_next_customer_code
from app.extensions import db

client = app.test_client()
results = []


def check(label, cond, extra=""):
    results.append((label, bool(cond)))
    print(f"[{'PASS' if cond else 'FAIL'}] {label}" + (f"  -> {extra}" if extra else ""))


TEST_NAME = "Zz Test Customer Auto"
TEST_NAME2 = "Zz Test Customer Auto Renamed"
TEMP_STATE = "Zz Test State Customer"

temp_state_id = None


def cleanup_test_customers():
    for c in Customer.query.filter(Customer.name.in_([TEST_NAME, TEST_NAME2])).all():
        led_id = c.ledger_id
        db.session.delete(c)
        db.session.commit()
        led = Ledger.query.get(led_id) if led_id else None
        if led:
            db.session.delete(led)
            db.session.commit()


with app.app_context():
    cleanup_test_customers()

    state = State.query.filter(State.is_deleted == False).first()
    if state is None:
        state = State(code="ZZC", name=TEMP_STATE, gst_state_code="99",
                      is_active=True, is_deleted=False)
        db.session.add(state)
        db.session.commit()
        temp_state_id = state.id
    state_id = state.id

check("Found a state for FK", state_id is not None, f"state_id={state_id}")

resp = client.get("/customers")
html = resp.get_data(as_text=True)
check("GET /customers returns 200", resp.status_code == 200, f"status={resp.status_code}")

with app.app_context():
    expected_next = generate_next_customer_code()

check(
    'List page shows disabled code input with next_code value',
    (f'name="code" value="{expected_next}" disabled' in html),
    f"expected_next={expected_next}",
)

resp = client.post(
    "/customers/add",
    data={"code": "HACK99", "name": TEST_NAME, "state_id": state_id, "opening_balance": "0"},
    follow_redirects=False,
)
check("POST /customers/add redirects (302)", resp.status_code in (302, 303), f"status={resp.status_code}")

created_id = None
with app.app_context():
    c = Customer.query.filter_by(name=TEST_NAME).first()
    created_id = c.id if c else None
    check("Customer created in DB", c is not None)
    if c:
        check("Auto code used (bogus 'HACK99' ignored)", c.code == expected_next, f"code={c.code}")
        check("Ledger created + linked", c.ledger_id is not None, f"ledger_id={c.ledger_id}")

with app.app_context():
    after = generate_next_customer_code()
serial = int(expected_next.split("-")[1])
exp_after = f"C-{serial + 1:04d}"
check("Next code increments after add", after == exp_after, f"after={after} expected={exp_after}")

if created_id:
    resp = client.post(
        f"/customers/edit/{created_id}",
        data={"code": "HACKED", "name": TEST_NAME2, "state_id": state_id, "opening_balance": "0"},
        follow_redirects=False,
    )
    check("POST /customers/edit redirects (302)", resp.status_code in (302, 303), f"status={resp.status_code}")

    with app.app_context():
        c = Customer.query.get(created_id)
        check("Edit kept code immutable", c.code == expected_next, f"code={c.code}")
        check("Edit updated name", c.name == TEST_NAME2, f"name={c.name}")

with app.app_context():
    cleanup_test_customers()
    check("Cleanup: test customer removed", Customer.query.filter(Customer.name.in_([TEST_NAME, TEST_NAME2])).first() is None)

    if temp_state_id:
        s = State.query.get(temp_state_id)
        if s:
            db.session.delete(s)
            db.session.commit()

passed = sum(1 for _, ok in results if ok)
total = len(results)
print(f"\nTOTAL: {passed}/{total} passed")
sys.exit(0 if passed == total else 1)
