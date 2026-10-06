import _guard  # Safety: asli erp.db pe chalti hai — bina ERP_ALLOW_DB_SCRIPTS=1 ke ruk jaayegi (dekho _guard.py)
# Vendor <-> Vendor Type Master FK connection verify (test data cleaned up at end)
from app import app
from app.models import Vendor, VendorType, State, Ledger
from app.extensions import db
import sqlalchemy as sa

client = app.test_client()
results = []


def check(label, cond, extra=""):
    results.append(("PASS" if cond else "FAIL", label, extra))


TEST_CODE = "VTTEST1"
TMP_CODE = "VT-TESTX"

# Safety: agar pichhle run se test data bacha ho to pehle hata do
with app.app_context():
    for code in (TEST_CODE, "VTTEST2", "VTTEST3", "VTTEST4"):
        for v in Vendor.query.filter_by(code=code).all():
            Ledger.query.filter_by(id=v.ledger_id).delete()
            db.session.delete(v)
    VendorType.query.filter_by(code=TMP_CODE).delete()
    db.session.commit()

# ---- Schema: vendors table me ab sirf vendor_type_id (FK) hai, purana text nahi ----
with app.app_context():
    cols = [c[1] for c in db.session.execute(sa.text("PRAGMA table_info(vendors)")).fetchall()]
check("vendors has vendor_type_id column", "vendor_type_id" in cols, str(cols))
check("vendors old 'vendor_type' text column dropped", "vendor_type" not in cols)

# ---- Backfill: purane text values ab master rows se jud gaye ----
with app.app_context():
    rms = VendorType.query.filter_by(name="Raw Material Supplier").first()
    trans = VendorType.query.filter_by(name="Transporter").first()
    check("master has 'Raw Material Supplier'", rms is not None)
    check("master has 'Transporter'", trans is not None)
    rms_id = rms.id if rms else None
    trans_id = trans.id if trans else None
    rms_vendor_count = Vendor.query.filter(Vendor.vendor_type_id == rms_id).count() if rms_id else 0
    trans_vendor_count = Vendor.query.filter(Vendor.vendor_type_id == trans_id).count() if trans_id else 0
check("backfilled vendors -> Raw Material Supplier", rms_vendor_count >= 5, "count=%d" % rms_vendor_count)
check("backfilled vendors -> Transporter", trans_vendor_count >= 1, "count=%d" % trans_vendor_count)

# ---- List page: dropdown ab Vendor Type Master se ----
with app.app_context():
    guj = State.query.filter_by(name="Gujarat").first()
    guj_id = guj.id
r = client.get("/vendors")
check("GET /vendors -> 200", r.status_code == 200, str(r.status_code))
check("template rendered (tbody present)", b"vendors-tbody" in r.data)
check("dropdown select name=vendor_type_id present", b'name="vendor_type_id"' in r.data)
check("old select name=\"vendor_type\" gone", b'name="vendor_type"' not in r.data)
check("dropdown option value = VendorType.id (Transporter)", ('value="%d"' % trans_id).encode() in r.data)
check("dropdown option text = VendorType.name (Transporter)", b">Transporter</option>" in r.data)
check("optional blank option present", b"Select type" in r.data)

# ---- Add vendor with valid type (nullable FK) ----
r = client.post("/vendors/add", data={
    "code": TEST_CODE, "name": "Test Vendor Type FK",
    "state_id": str(guj_id), "vendor_type_id": str(trans_id),
    "opening_balance": "0", "opening_balance_type": "Cr",
}, follow_redirects=True)
check("add-with-type flash success", b"Vendor saved" in r.data, str(r.status_code))
with app.app_context():
    v = Vendor.query.filter_by(code=TEST_CODE).first()
    check("vendor stored with vendor_type_id", bool(v) and v.vendor_type_id == trans_id,
          str(v.vendor_type_id) if v else "none")
    check("relationship -> Transporter", bool(v) and v.vendor_type is not None and v.vendor_type.name == "Transporter",
          v.vendor_type.name if v and v.vendor_type else "none")
    check("auto ledger still created", bool(v) and v.ledger_id is not None)
    vid = v.id

# ---- Add vendor WITHOUT type (optional / nullable) ----
r = client.post("/vendors/add", data={
    "code": "VTTEST2", "name": "No Type Vendor",
    "state_id": str(guj_id), "opening_balance": "0", "opening_balance_type": "Cr",
}, follow_redirects=True)
check("add-without-type allowed (flash success)", b"Vendor saved" in r.data)
with app.app_context():
    v2 = Vendor.query.filter_by(code="VTTEST2").first()
    check("optional type stored as NULL", bool(v2) and v2.vendor_type_id is None,
          str(v2.vendor_type_id) if v2 else "none")

# ---- Add vendor with INVALID type id -> flash error, no create ----
r = client.post("/vendors/add", data={
    "code": "VTTEST3", "name": "Bad Type Vendor",
    "state_id": str(guj_id), "vendor_type_id": "99999",
    "opening_balance": "0", "opening_balance_type": "Cr",
}, follow_redirects=True)
check("invalid vendor_type_id flashes error", b"valid vendor type" in r.data)
with app.app_context():
    check("invalid type vendor not created", Vendor.query.filter_by(code="VTTEST3").first() is None)
    check("invalid type did not create ledger", Ledger.query.filter_by(name="Bad Type Vendor").first() is None)

# ---- Edit: change type Transporter -> Raw Material Supplier ----
r = client.post("/vendors/edit/%d" % vid, data={
    "code": TEST_CODE, "name": "Test Vendor Type FK",
    "state_id": str(guj_id), "vendor_type_id": str(rms_id),
    "opening_balance": "0", "opening_balance_type": "Cr",
}, follow_redirects=True)
check("edit flash success", b"Vendor Updated" in r.data)
with app.app_context():
    v = Vendor.query.get(vid)
    check("edit changed vendor_type_id", v.vendor_type_id == rms_id, str(v.vendor_type_id))
    check("edit relationship reflects new type", v.vendor_type.name == "Raw Material Supplier",
          v.vendor_type.name if v.vendor_type else "none")

# ---- Edit: clear type back to blank (optional still works) ----
r = client.post("/vendors/edit/%d" % vid, data={
    "code": TEST_CODE, "name": "Test Vendor Type FK",
    "state_id": str(guj_id),
    "opening_balance": "0", "opening_balance_type": "Cr",
}, follow_redirects=True)
with app.app_context():
    v = Vendor.query.get(vid)
    check("edit can clear type to NULL (optional)", v.vendor_type_id is None, str(v.vendor_type_id))

# ---- Master rename turant vendor list me dikhna chahiye (relationship live) ----
with app.app_context():
    tmp = VendorType(code=TMP_CODE, name="Temp Type For Verify", is_active=True, is_deleted=False)
    db.session.add(tmp)
    db.session.commit()
    tmp_id = tmp.id
client.post("/vendors/edit/%d" % vid, data={
    "code": TEST_CODE, "name": "Test Vendor Type FK",
    "state_id": str(guj_id), "vendor_type_id": str(tmp_id),
    "opening_balance": "0", "opening_balance_type": "Cr",
}, follow_redirects=True)
with app.app_context():
    tmp = VendorType.query.get(tmp_id)
    tmp.name = "Temp Type Renamed"
    db.session.commit()
r = client.get("/vendors")
check("list reflects renamed master type (View data attr)", b"Temp Type Renamed" in r.data)

# ---- Soft-deleted type: add pe reject + dropdown se hidden ----
with app.app_context():
    tmp = VendorType.query.get(tmp_id)
    tmp.is_deleted = True
    db.session.commit()
r = client.post("/vendors/add", data={
    "code": "VTTEST4", "name": "Deleted Type Vendor",
    "state_id": str(guj_id), "vendor_type_id": str(tmp_id),
    "opening_balance": "0", "opening_balance_type": "Cr",
}, follow_redirects=True)
check("soft-deleted type flashes 'valid vendor type'", b"valid vendor type" in r.data)
with app.app_context():
    check("soft-deleted type vendor not created", Vendor.query.filter_by(code="VTTEST4").first() is None)
r = client.get("/vendors")
# NOTE: sirf value="id" se check nahi kar sakte — State dropdown me bhi chhote ids
# aate hain, isliye poora option tag (value + type name) match karte hain.
check("soft-deleted type hidden from dropdown",
      ('<option value="%d">Temp Type Renamed</option>' % tmp_id).encode() not in r.data)

# ---- Cleanup ----
with app.app_context():
    for code in (TEST_CODE, "VTTEST2", "VTTEST3", "VTTEST4"):
        for v in Vendor.query.filter_by(code=code).all():
            Ledger.query.filter_by(id=v.ledger_id).delete()
            db.session.delete(v)
    VendorType.query.filter_by(code=TMP_CODE).delete()
    db.session.commit()
    check("cleanup: test vendors gone", Vendor.query.filter_by(code=TEST_CODE).first() is None)
    check("cleanup: temp type gone", VendorType.query.filter_by(code=TMP_CODE).first() is None)

for status, label, extra in results:
    print("%s - %s%s" % (status, label, " [" + extra + "]" if extra else ""))
print("TOTAL:", sum(1 for x in results if x[0] == "PASS"), "/", len(results))
