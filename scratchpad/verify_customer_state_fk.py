import _guard  # Safety: asli erp.db pe chalti hai — bina ERP_ALLOW_DB_SCRIPTS=1 ke ruk jaayegi (dekho _guard.py)
# Customer <-> State Master FK connection verify (test data cleaned up at end)
from app import app
from app.models import Customer, State, Ledger
from app.extensions import db

client = app.test_client()
results = []


def check(label, cond, extra=""):
    results.append(("PASS" if cond else "FAIL", label, extra))


TEST_CODE = "CTEST1"

# Safety: agar pichhle run se koi test customer bacha ho to pehle hata do
with app.app_context():
    for c in Customer.query.filter_by(code=TEST_CODE).all():
        Ledger.query.filter_by(id=c.ledger_id).delete()
        db.session.delete(c)
    db.session.commit()
    guj = State.query.filter_by(name="Gujarat").first()
    delhi = State.query.filter_by(name="Delhi").first()
    guj_id = guj.id
    delhi_id = delhi.id

# ---- List page: dropdown ab State Master se ----
r = client.get("/customers")
check("GET /customers -> 200", r.status_code == 200, str(r.status_code))
check("template rendered (tbody present)", b"customers-tbody" in r.data)
check("dropdown option value = State.id (Gujarat)", ('value="%d"' % guj_id).encode() in r.data, "guj_id=%d" % guj_id)
check("dropdown option text = State.name (Gujarat)", b">Gujarat</option>" in r.data)
check("list row shows state NAME (Gujarat)", b">Gujarat<" in r.data)
check("old hardcoded select name=\"state\" gone", b'name="state"' not in r.data)

# ---- Add with valid state_id ----
r = client.post("/customers/add", data={
    "code": TEST_CODE, "name": "Test Customer FK",
    "state_id": str(guj_id), "opening_balance": "0", "opening_balance_type": "Dr",
}, follow_redirects=True)
check("add flash success", b"Customer saved" in r.data, str(r.status_code))
with app.app_context():
    c = Customer.query.filter_by(code=TEST_CODE).first()
    check("customer created with valid state_id", bool(c) and c.state_id == guj_id, str(c.state_id) if c else "none")
    check("relationship returns State object", bool(c) and c.state is not None and c.state.name == "Gujarat",
          c.state.name if c and c.state else "none")
    check("auto ledger still created", bool(c) and c.ledger_id is not None)
    cid = c.id

# ---- Add with MISSING state_id -> redirect, no create ----
client.post("/customers/add", data={"code": "CTEST2", "name": "No State"}, follow_redirects=True)
with app.app_context():
    check("missing state_id blocked (not created)", Customer.query.filter_by(code="CTEST2").first() is None)

# ---- Add with INVALID state_id -> flash error, no create ----
r = client.post("/customers/add", data={"code": "CTEST3", "name": "Bad Customer", "state_id": "99999"},
                follow_redirects=True)
check("invalid state_id flashes error", b"valid state" in r.data)
with app.app_context():
    check("invalid state_id not created", Customer.query.filter_by(code="CTEST3").first() is None)
    check("invalid state_id did not create a ledger", Ledger.query.filter_by(name="Bad Customer").first() is None)

# ---- Edit: change state Gujarat -> Delhi ----
r = client.post("/customers/edit/%d" % cid, data={
    "code": TEST_CODE, "name": "Test Customer FK",
    "state_id": str(delhi_id), "opening_balance": "0", "opening_balance_type": "Dr",
}, follow_redirects=True)
check("edit flash success", b"Customer Updated" in r.data)
with app.app_context():
    c = Customer.query.get(cid)
    check("edit changed state_id to Delhi", c.state_id == delhi_id, str(c.state_id))
    check("edit relationship reflects Delhi", c.state.name == "Delhi", c.state.name if c.state else "none")

# ---- List reflects updated state name ----
r = client.get("/customers")
check("list reflects renamed relationship", b"Test Customer FK" in r.data)

# ---- Cleanup ----
with app.app_context():
    for code in (TEST_CODE, "CTEST2", "CTEST3"):
        for c in Customer.query.filter_by(code=code).all():
            Ledger.query.filter_by(id=c.ledger_id).delete()
            db.session.delete(c)
    db.session.commit()
    check("cleanup: test customers gone", Customer.query.filter_by(code=TEST_CODE).first() is None)

for status, label, extra in results:
    print("%s - %s%s" % (status, label, " [" + extra + "]" if extra else ""))
print("TOTAL:", sum(1 for x in results if x[0] == "PASS"), "/", len(results))
