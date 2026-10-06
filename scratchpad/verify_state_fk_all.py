import _guard  # Safety: asli erp.db pe chalti hai — bina ERP_ALLOW_DB_SCRIPTS=1 ke ruk jaayegi (dekho _guard.py)
# STEP 5 - Final combined verify: Vendor + Customer + Branch sab State Master se
# connected hain, aur State ka rename teeno jagah reflect hota hai.
# (Test data end me clean ho jaata hai.)
from app import app
from app.models import Vendor, Customer, Branch, State, Ledger
from app.extensions import db
from sqlalchemy import inspect

client = app.test_client()
results = []


def check(label, cond, extra=""):
    results.append(("PASS" if cond else "FAIL", label, extra))


V_CODE = "ZZV1"
C_CODE = "ZZC1"
B_NAME = "ZZ Test Branch Step5"
RENAMED = "ZZ Gujarat Renamed"

# ---- Safety: pichhle run ka koi leftover test data pehle hata do ----
with app.app_context():
    for v in Vendor.query.filter_by(code=V_CODE).all():
        if v.ledger_id:
            Ledger.query.filter_by(id=v.ledger_id).delete()
        db.session.delete(v)
    for c in Customer.query.filter_by(code=C_CODE).all():
        if c.ledger_id:
            Ledger.query.filter_by(id=c.ledger_id).delete()
        db.session.delete(c)
    for b in Branch.query.filter_by(name=B_NAME).all():
        db.session.delete(b)
    db.session.commit()

    guj = State.query.filter_by(name="Gujarat").first()
    delhi = State.query.filter_by(name="Delhi").first()
    guj_id, delhi_id = guj.id, delhi.id
    guj_gst = guj.gst_state_code
    states_before = State.query.count()

# ---- 1) SCHEMA: teeno tables me state_id FK hai, purana text 'state' gaya ----
with app.app_context():
    insp = inspect(db.engine)
    for tbl in ("vendors", "customers", "branches"):
        cols = [c["name"] for c in insp.get_columns(tbl)]
        fks = insp.get_foreign_keys(tbl)
        has_state_id = "state_id" in cols
        no_text_state = "state" not in cols
        fk_ok = any(
            "state_id" in (fk.get("constrained_columns") or [])
            and (fk.get("referred_table") == "states")
            for fk in fks
        )
        check("%s: state_id column present" % tbl, has_state_id, str(cols))
        check("%s: old text 'state' column removed" % tbl, no_text_state)
        check("%s: state_id -> states.id FK" % tbl, fk_ok, str(fks))

# ---- 1b) Step 4 proof: legacy INDIAN_STATES list gone ----
# NOTE: `import app.constants` se local naam `app` module ban jaata, isliye importlib.
import importlib
try:
    _const = importlib.import_module("app.constants")
    check("app.constants still imports fine", True)
except Exception as _e:  # noqa: BLE001
    _const = None
    check("app.constants still imports fine", False, str(_e))
legacy_gone = (not hasattr(_const, "INDIAN_STATES")) if _const else False
check("legacy INDIAN_STATES list removed", legacy_gone)

# ---- 2) ADD: teeno masters valid state_id ke saath ----
r = client.post("/vendors/add", data={
    "code": V_CODE, "name": "ZZ Test Vendor Step5",
    "state_id": str(guj_id), "opening_balance": "0", "opening_balance_type": "Cr",
}, follow_redirects=True)
check("VENDOR add flash success", b"Vendor saved" in r.data)

r = client.post("/customers/add", data={
    "code": C_CODE, "name": "ZZ Test Customer Step5",
    "state_id": str(guj_id), "opening_balance": "0", "opening_balance_type": "Dr",
}, follow_redirects=True)
check("CUSTOMER add flash success", b"Customer saved" in r.data)

r = client.post("/warehouses/branches/add", data={"name": B_NAME, "state_id": str(guj_id), "gstin": ""})
bdata = r.get_json() or {}
check("BRANCH add returns success", bool(bdata.get("success")), str(bdata))

with app.app_context():
    v = Vendor.query.filter_by(code=V_CODE).first()
    c = Customer.query.filter_by(code=C_CODE).first()
    b = Branch.query.filter_by(name=B_NAME).first()
    check("VENDOR created with valid state_id", bool(v) and v.state_id == guj_id, str(v.state_id) if v else "none")
    check("VENDOR relationship = State object", bool(v) and v.state is not None and v.state.name == "Gujarat",
          v.state.name if v and v.state else "none")
    check("CUSTOMER created with valid state_id", bool(c) and c.state_id == guj_id, str(c.state_id) if c else "none")
    check("CUSTOMER relationship = State object", bool(c) and c.state is not None and c.state.name == "Gujarat",
          c.state.name if c and c.state else "none")
    check("BRANCH created with valid state_id", bool(b) and b.state_id == guj_id, str(b.state_id) if b else "none")
    check("BRANCH relationship = State object", bool(b) and b.state is not None and b.state.name == "Gujarat",
          b.state.name if b and b.state else "none")
    v_id = v.id if v else None
    c_id = c.id if c else None
    b_id = b.id if b else None

# ---- 3) STATE RENAME (real State Master edit route) -> reflection check ----
# NOTE: rename wo waqt karte hain jab teeno (Vendor/Customer/Branch) Gujarat pe hain,
# taaki relationship + FK dono ka asar saaf dikhe. Edit (Delhi) test rename ke BAAD.
r = client.post("/states/edit/%d" % guj_id, data={"name": RENAMED, "gst_state_code": guj_gst},
                follow_redirects=True)
check("STATE edit flash success", b"State updated" in r.data)

with app.app_context():
    g = State.query.get(guj_id)
    check("STATE rename applied in DB", g.name == RENAMED, g.name)
    check("STATE id unchanged after rename", g.id == guj_id, str(g.id))
    check("STATE count unchanged (no duplicate)", State.query.count() == states_before,
          "%d -> %d" % (states_before, State.query.count()))
    v = Vendor.query.get(v_id)
    c = Customer.query.get(c_id)
    b = Branch.query.get(b_id)
    check("VENDOR FK unchanged by rename", v.state_id == guj_id, str(v.state_id))
    check("CUSTOMER FK unchanged by rename", c.state_id == guj_id, str(c.state_id))
    check("BRANCH FK unchanged by rename", b.state_id == guj_id, str(b.state_id))
    # Relationship ab NAYA naam dikhaye (rename ka asar - koi duplicate row nahi bana)
    check("VENDOR relationship reflects renamed state", v.state.name == RENAMED, v.state.name if v.state else "none")
    check("CUSTOMER relationship reflects renamed state", c.state.name == RENAMED, c.state.name if c.state else "none")
    check("BRANCH relationship reflects renamed state", b.state.name == RENAMED, b.state.name if b.state else "none")

# HTML pages pe rename dikhna chahiye (list + dropdown, sab State Master se)
r = client.get("/vendors")
check("VENDOR list shows renamed state name", RENAMED.encode() in r.data)
r = client.get("/customers")
check("CUSTOMER list shows renamed state name", RENAMED.encode() in r.data)
r = client.get("/warehouses")
check("BRANCH dropdown shows renamed option value=id",
      ('value="%d"' % guj_id).encode() in r.data, "guj_id=%d" % guj_id)
check("BRANCH dropdown option text = renamed name", (">%s</option>" % RENAMED).encode() in r.data)
r = client.get("/purchase_orders")
check("PO page still renders after rename (200)", r.status_code == 200, str(r.status_code))

# ---- 3b) Rename revert -> dropdown wapas Gujarat ----
r = client.post("/states/edit/%d" % guj_id, data={"name": "Gujarat", "gst_state_code": guj_gst},
                follow_redirects=True)
check("STATE revert flash success", b"State updated" in r.data)
with app.app_context():
    check("STATE name reverted to Gujarat", State.query.get(guj_id).name == "Gujarat")
r = client.get("/vendors")
check("VENDOR dropdown back to Gujarat", b">Gujarat</option>" in r.data)

# ---- 4) EDIT: Vendor + Customer ka state Gujarat -> Delhi (edit route check) ----
r = client.post("/vendors/edit/%d" % v_id, data={
    "code": V_CODE, "name": "ZZ Test Vendor Step5",
    "state_id": str(delhi_id), "opening_balance": "0", "opening_balance_type": "Cr",
}, follow_redirects=True)
check("VENDOR edit flash success", b"Vendor Updated" in r.data)

r = client.post("/customers/edit/%d" % c_id, data={
    "code": C_CODE, "name": "ZZ Test Customer Step5",
    "state_id": str(delhi_id), "opening_balance": "0", "opening_balance_type": "Dr",
}, follow_redirects=True)
check("CUSTOMER edit flash success", b"Customer Updated" in r.data)

with app.app_context():
    v = Vendor.query.get(v_id)
    c = Customer.query.get(c_id)
    check("VENDOR edit -> Delhi", v.state_id == delhi_id and v.state.name == "Delhi",
          "%s/%s" % (v.state_id, v.state.name if v.state else "none"))
    check("CUSTOMER edit -> Delhi", c.state_id == delhi_id and c.state.name == "Delhi",
          "%s/%s" % (c.state_id, c.state.name if c.state else "none"))
    # Branch me edit route nahi hai -> relationship object hi verify karo
    b = Branch.query.get(b_id)
    check("BRANCH relationship object intact (Gujarat)", b.state is not None and b.state.name == "Gujarat",
          b.state.name if b.state else "none")

# ---- 5) CLEANUP ----
with app.app_context():
    for v in Vendor.query.filter_by(code=V_CODE).all():
        if v.ledger_id:
            Ledger.query.filter_by(id=v.ledger_id).delete()
        db.session.delete(v)
    for c in Customer.query.filter_by(code=C_CODE).all():
        if c.ledger_id:
            Ledger.query.filter_by(id=c.ledger_id).delete()
        db.session.delete(c)
    for b in Branch.query.filter_by(name=B_NAME).all():
        db.session.delete(b)
    db.session.commit()
    check("cleanup: test vendor gone", Vendor.query.filter_by(code=V_CODE).first() is None)
    check("cleanup: test customer gone", Customer.query.filter_by(code=C_CODE).first() is None)
    check("cleanup: test branch gone", Branch.query.filter_by(name=B_NAME).first() is None)
    check("cleanup: state count restored", State.query.count() == states_before,
          str(State.query.count()))

for status, label, extra in results:
    print("%s - %s%s" % (status, label, " [" + extra + "]" if extra else ""))
print("TOTAL:", sum(1 for x in results if x[0] == "PASS"), "/", len(results))
