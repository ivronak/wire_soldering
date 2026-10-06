import _guard  # Safety: asli erp.db pe chalti hai — bina ERP_ALLOW_DB_SCRIPTS=1 ke ruk jaayegi (dekho _guard.py)
# Branch <-> State Master FK connection verify (test data cleaned up at end)
from app import app
from app.models import Branch, State
from app.extensions import db

client = app.test_client()
results = []


def check(label, cond, extra=""):
    results.append(("PASS" if cond else "FAIL", label, extra))


VALID_NAME = "ZB Test Branch FK"
MISSING_NAME = "ZB No State Branch"
INVALID_NAME = "ZB Bad State Branch"

# Safety: agar pichhle run se test branches bache ho to pehle hata do
with app.app_context():
    for n in (VALID_NAME, MISSING_NAME, INVALID_NAME):
        for b in Branch.query.filter_by(name=n).all():
            db.session.delete(b)
    db.session.commit()
    guj = State.query.filter_by(name="Gujarat").first()
    delhi = State.query.filter_by(name="Delhi").first()
    guj_id = guj.id
    delhi_id = delhi.id
    existing_ids = [(b.id, b.state_id) for b in Branch.query.all()]

# ---- List page: branch inline state dropdown ab State Master se ----
r = client.get("/warehouses")
check("GET /warehouses -> 200", r.status_code == 200, str(r.status_code))
check("template rendered (branch-inline present)", b"branch-inline" in r.data)
check("state dropdown option value = State.id (Gujarat)", ('value="%d"' % guj_id).encode() in r.data, "guj_id=%d" % guj_id)
check("state dropdown option text = State.name (Gujarat)", b">Gujarat</option>" in r.data)
check("old hardcoded option value=\"Gujarat\" gone", b'value="Gujarat"' not in r.data)
check("branch dropdown still shows branch names", b"Mehsana Branch" in r.data)

# ---- Existing branches backfilled (text -> id) ----
check("existing branches backfilled to state_id", all(sid == guj_id for (_id, sid) in existing_ids), str(existing_ids))

# ---- Add branch with valid state_id (fetch/json route) ----
r = client.post("/warehouses/branches/add", data={"name": VALID_NAME, "state_id": str(guj_id), "gstin": ""})
data = r.get_json() or {}
check("add branch returns success", bool(data.get("success")), str(data))
with app.app_context():
    b = Branch.query.filter_by(name=VALID_NAME).first()
    check("branch created with valid state_id", bool(b) and b.state_id == guj_id, str(b.state_id) if b else "none")
    check("relationship returns State object", bool(b) and b.state is not None and b.state.name == "Gujarat",
          b.state.name if b and b.state else "none")
    check("response id matches created row", bool(b) and data.get("id") == b.id,
          "%s vs %s" % (data.get("id"), b.id if b else None))

# ---- Add with MISSING state_id -> json error, no create ----
r = client.post("/warehouses/branches/add", data={"name": MISSING_NAME, "gstin": ""})
data = r.get_json() or {}
check("missing state_id rejected", data.get("success") is False, str(data))
with app.app_context():
    check("missing state_id not created", Branch.query.filter_by(name=MISSING_NAME).first() is None)

# ---- Add with INVALID state_id -> json error, no create ----
r = client.post("/warehouses/branches/add", data={"name": INVALID_NAME, "state_id": "99999", "gstin": ""})
data = r.get_json() or {}
check("invalid state_id rejected", data.get("success") is False, str(data))
check("invalid state_id error mentions valid state", "valid state" in (data.get("error") or "").lower(), str(data.get("error")))
with app.app_context():
    check("invalid state_id not created", Branch.query.filter_by(name=INVALID_NAME).first() is None)

# ---- PO page still renders (uses branch.state.name for intra/inter compare) ----
r = client.get("/purchase_orders")
check("GET /purchase_orders -> 200", r.status_code == 200, str(r.status_code))

# ---- New branch usable in warehouse list branch dropdown ----
r = client.get("/warehouses")
check("new branch appears in branch dropdown", VALID_NAME.encode() in r.data)

# ---- Cleanup ----
with app.app_context():
    for n in (VALID_NAME, MISSING_NAME, INVALID_NAME):
        for b in Branch.query.filter_by(name=n).all():
            db.session.delete(b)
    db.session.commit()
    check("cleanup: test branches gone", Branch.query.filter_by(name=VALID_NAME).first() is None)

for status, label, extra in results:
    print("%s - %s%s" % (status, label, " [" + extra + "]" if extra else ""))
print("TOTAL:", sum(1 for x in results if x[0] == "PASS"), "/", len(results))
