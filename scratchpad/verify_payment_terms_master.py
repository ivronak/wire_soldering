import _guard  # Safety: asli erp.db pe chalti hai — bina ERP_ALLOW_DB_SCRIPTS=1 ke ruk jaayegi (dekho _guard.py)
# Payment Terms Master (Step 0) verify — test data cleaned up at the end.
import sys
from app import app
from app.extensions import db
from app.models import PaymentTerm

results = []


def check(label, cond, extra=""):
    results.append((label, bool(cond), extra))


# ---------- 1. Table + seed ----------
with app.app_context():
    inspector = db.inspect(db.engine)
    tables = inspector.get_table_names()
    check("payment_terms table exists", "payment_terms" in tables)

    cols = {c["name"] for c in inspector.get_columns("payment_terms")} if "payment_terms" in tables else set()
    for col in ("id", "code", "name", "is_active", "is_deleted"):
        check("payment_terms.%s column" % col, col in cols)

    rows = PaymentTerm.query.order_by(PaymentTerm.id).all()
    check("seed has 5 rows", len(rows) == 5, "got %d" % len(rows))
    names = [r.name for r in rows]
    check("seed names match old options",
          names == ["Advance", "Net 15", "Net 30", "Net 45", "Net 60"], str(names))
    codes = [r.code for r in rows]
    check("seed codes PT-0001..PT-0005",
          codes == ["PT-0001", "PT-0002", "PT-0003", "PT-0004", "PT-0005"], str(codes))
    check("all seed rows active + not deleted",
          all(r.is_active and not r.is_deleted for r in rows))

# ---------- 2. Screen renders ----------
client = app.test_client()

r = client.get("/payment_terms")
check("GET /payment_terms -> 200", r.status_code == 200, "got %d" % r.status_code)
body = r.data
check("screen shows title", b"Payment terms master" in body)
check("screen lists PT-0001", b"PT-0001" in body)
check("screen lists Net 30 option row", b"Net 30" in body)
check("next auto code PT-0006 shown", b"PT-0006" in body)

# ---------- 3. Add ----------
r = client.post("/payment_terms/add", data={"name": "Temp Term"}, follow_redirects=True)
check("add -> 200", r.status_code == 200)
with app.app_context():
    tmp = PaymentTerm.query.filter_by(name="Temp Term").first()
    check("added row exists", tmp is not None)
    tmp_id = tmp.id if tmp else None
    check("added row auto code PT-0006", tmp and tmp.code == "PT-0006", tmp.code if tmp else "")

# ---------- 4. Edit / rename ----------
r = client.post("/payment_terms/edit/%d" % tmp_id, data={"name": "Temp Term Renamed"}, follow_redirects=True)
check("edit -> 200", r.status_code == 200)
with app.app_context():
    tmp = PaymentTerm.query.get(tmp_id)
    check("edit renamed row", tmp.name == "Temp Term Renamed", tmp.name if tmp else "")

r = client.get("/payment_terms")
check("renamed name reflects in list", b"Temp Term Renamed" in r.data)

# ---------- 5. Toggle active/stopped ----------
client.post("/payment_terms/toggle/%d" % tmp_id, follow_redirects=True)
with app.app_context():
    check("toggle -> is_active False", PaymentTerm.query.get(tmp_id).is_active is False)
client.post("/payment_terms/toggle/%d" % tmp_id, follow_redirects=True)
with app.app_context():
    check("toggle again -> is_active True", PaymentTerm.query.get(tmp_id).is_active is True)

# ---------- 6. Soft delete ----------
client.post("/payment_terms/delete/%d" % tmp_id, follow_redirects=True)
with app.app_context():
    tmp = PaymentTerm.query.get(tmp_id)
    check("soft-delete sets is_deleted", tmp.is_deleted is True)
    check("soft-deleted row kept in DB", tmp is not None)
r = client.get("/payment_terms")
check("soft-deleted hidden from list",
      b"Temp Term Renamed" not in r.data)

# ---------- 7. Blank name rejected (no crash) ----------
before = None
with app.app_context():
    before = PaymentTerm.query.count()
client.post("/payment_terms/add", data={"name": "   "}, follow_redirects=True)
with app.app_context():
    check("blank name does not create row", PaymentTerm.query.count() == before)

# ---------- 8. Sidebar link present ----------
r = client.get("/payment_terms")
check("sidebar has Payment terms link", b"payment_terms" in r.data and b"Payment terms</a>" in r.data)

# ---------- cleanup ----------
with app.app_context():
    for row in PaymentTerm.query.filter(PaymentTerm.name.like("Temp Term%")).all():
        db.session.delete(row)
    db.session.commit()
    left = PaymentTerm.query.count()
    check("cleanup: back to 5 rows", left == 5, "got %d" % left)

# ---------- report ----------
passed = sum(1 for _, ok, _ in results if ok)
total = len(results)
print("=" * 60)
for label, ok, extra in results:
    print("%s %s%s" % ("PASS" if ok else "FAIL", label, ("  [%s]" % extra) if extra and not ok else ""))
print("=" * 60)
print("RESULT: %d/%d PASS" % (passed, total))
sys.exit(0 if passed == total else 1)
