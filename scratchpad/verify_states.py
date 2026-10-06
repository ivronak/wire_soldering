import _guard  # Safety: asli erp.db pe chalti hai — bina ERP_ALLOW_DB_SCRIPTS=1 ke ruk jaayegi (dekho _guard.py)
# Temporary verification script for the State Master (test data cleaned up at the end)
from app import app
from app.models import State
from app.extensions import db
from app.states.routes import generate_next_state_code

client = app.test_client()
results = []


def check(label, cond, extra=""):
    results.append(("PASS" if cond else "FAIL", label, extra))


# SAFETY GUARD: states table ab seed data (36 states/UT, migration fd2c563b95f7) se bhara hai.
# Yeh script pehle poori table wipe karti thi - ab wo seed ko udaa degi, isliye guard laga diya.
with app.app_context():
    existing = State.query.count()
    if existing:
        print("SKIP - states table me %d rows hain (seed data maujood)." % existing)
        print("Yeh verification script puri table delete karti hai, isliye abort kiya (seed bachane ke liye).")
        print("Fresh/empty DB par hi chalao.")
        raise SystemExit(0)

r = client.get("/states")
check("GET /states -> 200", r.status_code == 200, str(r.status_code))
check("page heading rendered", b"State master" in r.data)
check("next code shown (ST-0001)", b"ST-0001" in r.data)
check("empty state block present", b"No states found" in r.data)

r = client.post("/states/add", data={"name": "Gujarat", "gst_state_code": "24"}, follow_redirects=True)
check("add Gujarat flash", b"State saved" in r.data, str(r.status_code))
with app.app_context():
    s1 = State.query.filter_by(gst_state_code="24").first()
    check("auto code ST-0001", bool(s1) and s1.code == "ST-0001", s1.code if s1 else "none")
    check("row active and not deleted", bool(s1) and s1.is_active and not s1.is_deleted)
    sid = s1.id

r = client.post("/states/add", data={"name": "Dup", "gst_state_code": "24"}, follow_redirects=True)
check("duplicate GST code blocked", b"already used by Gujarat" in r.data)

r = client.post("/states/add", data={"name": "Bad", "gst_state_code": "7"}, follow_redirects=True)
check("1 digit GST rejected", b"must be 2 digits" in r.data)

r = client.post("/states/add", data={"name": "Bad2", "gst_state_code": "ab"}, follow_redirects=True)
check("non numeric GST rejected", b"must be 2 digits" in r.data)

r = client.post("/states/add", data={"name": "NoGst", "gst_state_code": ""}, follow_redirects=True)
check("empty GST rejected", b"required" in r.data)

r = client.post("/states/edit/%d" % sid, data={"name": "Gujarat State", "gst_state_code": "24"}, follow_redirects=True)
check("edit flash", b"State updated" in r.data)
with app.app_context():
    s = State.query.get(sid)
    check("name updated, code unchanged", s.name == "Gujarat State" and s.code == "ST-0001", "%s/%s" % (s.name, s.code))

client.post("/states/add", data={"name": "Maharashtra", "gst_state_code": "27"}, follow_redirects=True)
with app.app_context():
    mah = State.query.filter_by(gst_state_code="27").first()
    check("second state code ST-0002", bool(mah) and mah.code == "ST-0002", mah.code if mah else "none")
    mah_id = mah.id

r = client.post("/states/edit/%d" % mah_id, data={"name": "Maharashtra", "gst_state_code": "24"}, follow_redirects=True)
check("duplicate GST code blocked on edit", b"already used by" in r.data)

r = client.post("/states/toggle/%d" % sid, follow_redirects=True)
with app.app_context():
    check("toggle -> stopped", State.query.get(sid).is_active is False)
r = client.post("/states/toggle/%d" % sid, follow_redirects=True)
with app.app_context():
    check("toggle -> active again", State.query.get(sid).is_active is True)

r = client.post("/states/delete/%d" % sid, follow_redirects=True)
check("delete flash", b"removed from the list" in r.data)
with app.app_context():
    s = State.query.get(sid)
    check("soft delete flag set, row kept in DB", s is not None and s.is_deleted is True)
r = client.get("/states")
check("soft-deleted row hidden from list", b"Gujarat State" not in r.data)

# Restore branch: craft a soft-deleted row whose code equals the next generated code
with app.app_context():
    last_id = State.query.order_by(State.id.desc()).first().id
    craft_code = "ST-%04d" % (last_id + 2)
    db.session.add(State(code=craft_code, name="TEST CRAFT", gst_state_code="99", is_active=False, is_deleted=True))
    db.session.commit()
    new_id = State.query.order_by(State.id.desc()).first().id
    expect_code = "ST-%04d" % (new_id + 1)

r = client.post("/states/add", data={"name": "Restored State", "gst_state_code": "99"}, follow_redirects=True)
check("restore flash on add", b"restored" in r.data.lower())
with app.app_context():
    s = State.query.filter_by(code=expect_code).first()
    check("restored row live again with same code", bool(s) and s.is_deleted is False and s.name == "Restored State",
          "%s/%s" % (s.code, s.name) if s else "none")

# Sidebar link + active nav state
r = client.get("/states")
check("sidebar States link present", b"/states" in r.data)
check("active_nav marks States link", b'aria-current="page"' in r.data)

# Fresh-table behaviour
with app.app_context():
    State.query.delete()
    db.session.commit()
    check("empty table -> ST-0001", generate_next_state_code() == "ST-0001")

for status, label, extra in results:
    print("%s - %s%s" % (status, label, " [" + extra + "]" if extra else ""))
print("TOTAL:", sum(1 for x in results if x[0] == "PASS"), "/", len(results))
