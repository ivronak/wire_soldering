import _guard  # Safety: asli erp.db pe chalti hai — bina ERP_ALLOW_DB_SCRIPTS=1 ke ruk jaayegi (dekho _guard.py)
# Vendor <-> State Master FK connection verify (test data cleaned up at end)
from app import app
from app.models import Vendor, State, Ledger
from app.extensions import db

client = app.test_client()
results = []


def check(label, cond, extra=""):
    results.append(("PASS" if cond else "FAIL", label, extra))


TEST_CODE = "VTEST1"

# Safety: agar pichhle run se koi test vendor bacha ho to pehle hata do
with app.app_context():
    for v in Vendor.query.filter_by(code=TEST_CODE).all():
        Ledger.query.filter_by(id=v.ledger_id).delete()
        db.session.delete(v)
    db.session.commit()
    guj = State.query.filter_by(name="Gujarat").first()
    delhi = State.query.filter_by(name="Delhi").first()
    guj_id = guj.id
    delhi_id = delhi.id

# ---- List page: dropdown ab State Master se ----
r = client.get("/vendors")
check("GET /vendors -> 200", r.status_code == 200, str(r.status_code))
check("template rendered (tbody present)", b"vendors-tbody" in r.data)
check("dropdown option value = State.id (Gujarat)", ('value="%d"' % guj_id).encode() in r.data, "guj_id=%d" % guj_id)
check("dropdown option text = State.name (Gujarat)", b">Gujarat</option>" in r.data)
check("list row shows state NAME (Gujarat)", b">Gujarat<" in r.data)
check("old hardcoded select name=\"state\" gone", b'name="state"' not in r.data)

# ---- Add with valid state_id ----
r = client.post("/vendors/add", data={
    "code": TEST_CODE, "name": "Test Vendor FK",
    "state_id": str(guj_id), "opening_balance": "0", "opening_balance_type": "Cr",
}, follow_redirects=True)
check("add flash success", b"Vendor saved" in r.data, str(r.status_code))
with app.app_context():
    v = Vendor.query.filter_by(code=TEST_CODE).first()
    check("vendor created with valid state_id", bool(v) and v.state_id == guj_id, str(v.state_id) if v else "none")
    check("relationship returns State object", bool(v) and v.state is not None and v.state.name == "Gujarat",
          v.state.name if v and v.state else "none")
    check("auto ledger still created", bool(v) and v.ledger_id is not None)
    vid = v.id

# ---- Add with MISSING state_id -> redirect, no create ----
client.post("/vendors/add", data={"code": "VTEST2", "name": "No State"}, follow_redirects=True)
with app.app_context():
    check("missing state_id blocked (not created)", Vendor.query.filter_by(code="VTEST2").first() is None)

# ---- Add with INVALID state_id -> flash error, no create ----
r = client.post("/vendors/add", data={"code": "VTEST3", "name": "Bad State", "state_id": "99999"},
                follow_redirects=True)
check("invalid state_id flashes error", b"valid state" in r.data)
with app.app_context():
    check("invalid state_id not created", Vendor.query.filter_by(code="VTEST3").first() is None)
    check("invalid state_id did not create a ledger", Ledger.query.filter_by(name="Bad State").first() is None)

# ---- Edit: change state Gujarat -> Delhi ----
r = client.post("/vendors/edit/%d" % vid, data={
    "code": TEST_CODE, "name": "Test Vendor FK",
    "state_id": str(delhi_id), "opening_balance": "0", "opening_balance_type": "Cr",
}, follow_redirects=True)
check("edit flash success", b"Vendor Updated" in r.data)
with app.app_context():
    v = Vendor.query.get(vid)
    check("edit changed state_id to Delhi", v.state_id == delhi_id, str(v.state_id))
    check("edit relationship reflects Delhi", v.state.name == "Delhi", v.state.name if v.state else "none")

# ---- List reflects updated state name ----
r = client.get("/vendors")
check("list reflects renamed relationship", b"Test Vendor FK" in r.data)

# ---- Cleanup ----
with app.app_context():
    for code in (TEST_CODE, "VTEST2", "VTEST3"):
        for v in Vendor.query.filter_by(code=code).all():
            Ledger.query.filter_by(id=v.ledger_id).delete()
            db.session.delete(v)
    db.session.commit()
    check("cleanup: test vendors gone", Vendor.query.filter_by(code=TEST_CODE).first() is None)

for status, label, extra in results:
    print("%s - %s%s" % (status, label, " [" + extra + "]" if extra else ""))
print("TOTAL:", sum(1 for x in results if x[0] == "PASS"), "/", len(results))
