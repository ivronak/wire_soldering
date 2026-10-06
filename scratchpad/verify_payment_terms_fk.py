import _guard  # Safety: asli erp.db pe chalti hai — bina ERP_ALLOW_DB_SCRIPTS=1 ke ruk jaayegi (dekho _guard.py)
# Payment Terms <-> Master FK connection verify (Vendor + Customer + PO).
# Test data cleaned up at the end. Run: set PYTHONPATH=. && venv\Scripts\python.exe scratchpad\verify_payment_terms_fk.py
from app import app
from app.models import (Vendor, Customer, PurchaseOrder, PaymentTerm, State,
                        Ledger, Branch, Warehouse)
from app.extensions import db
import sqlalchemy as sa

client = app.test_client()
results = []


def check(label, cond, extra=""):
    results.append(("PASS" if cond else "FAIL", label, extra))


V_CODE = "VPTTEST1"
C_CODE = "CPTTEST1"
TMP_PT = "PTTESTX"
TMP_BR = "ZBRTEST"
TMP_WH = "ZWHPTTEST"


def cleanup():
    # Vendor test (ledger bhi hata do)
    for v in Vendor.query.filter_by(code=V_CODE).all():
        if v.ledger_id:
            Ledger.query.filter_by(id=v.ledger_id).delete()
        db.session.delete(v)
    # Customer test (ledger bhi hata do)
    for c in Customer.query.filter_by(code=C_CODE).all():
        if c.ledger_id:
            Ledger.query.filter_by(id=c.ledger_id).delete()
        db.session.delete(c)
    # PO test
    PurchaseOrder.query.filter(PurchaseOrder.remarks == "PT-FK-TEST").delete()
    # Warehouse / branch test (agar banaye ho)
    Warehouse.query.filter_by(code=TMP_WH).delete()
    Branch.query.filter_by(name=TMP_BR).delete()
    # Temp payment term
    PaymentTerm.query.filter_by(code=TMP_PT).delete()
    db.session.commit()


with app.app_context():
    cleanup()

# ---- Schema: teeno tables me ab `payment_terms_id` (FK) hai, purana text nahi ----
for table in ("vendors", "customers", "purchase_orders"):
    with app.app_context():
        cols = [c[1] for c in db.session.execute(sa.text("PRAGMA table_info(%s)" % table)).fetchall()]
    check("%s has payment_terms_id column" % table, "payment_terms_id" in cols, str(cols))
    check("%s old 'payment_terms' text column dropped" % table, "payment_terms" not in cols)

# ---- Master seeded (5 options) ----
with app.app_context():
    pts = PaymentTerm.query.order_by(PaymentTerm.id).all()
    names = [p.name for p in pts]
    check("master has 5 payment terms", len(pts) == 5, str(names))
    check("master names == old hardcoded options",
          names == ["Advance", "Net 15", "Net 30", "Net 45", "Net 60"], str(names))
    net30 = PaymentTerm.query.filter_by(name="Net 30").first()
    net15 = PaymentTerm.query.filter_by(name="Net 15").first()
    check("master has 'Net 30'", net30 is not None)
    check("master has 'Net 15'", net15 is not None)
    net30_id = net30.id if net30 else None
    net15_id = net15.id if net15 else None

# ---- Backfill: har non-null payment_terms_id valid master row ho ----
with app.app_context():
    master_ids = {p.id for p in PaymentTerm.query.all()}
    v_ids = [r[0] for r in db.session.execute(sa.text(
        "SELECT payment_terms_id FROM vendors WHERE payment_terms_id IS NOT NULL")).fetchall()]
    c_ids = [r[0] for r in db.session.execute(sa.text(
        "SELECT payment_terms_id FROM customers WHERE payment_terms_id IS NOT NULL")).fetchall()]
    po_ids = [r[0] for r in db.session.execute(sa.text(
        "SELECT payment_terms_id FROM purchase_orders WHERE payment_terms_id IS NOT NULL")).fetchall()]
check("all vendors.payment_terms_id valid (backfill integrity)",
      all(i in master_ids for i in v_ids), "vendors backfilled=%d" % len(v_ids))
check("all customers.payment_terms_id valid (backfill integrity)",
      all(i in master_ids for i in c_ids), "customers backfilled=%d" % len(c_ids))
check("all purchase_orders.payment_terms_id valid (backfill integrity)",
      all(i in master_ids for i in po_ids), "purchase_orders backfilled=%d" % len(po_ids))
check("backfill actually populated (kuch rows me terms hai)",
      (len(v_ids) + len(c_ids) + len(po_ids)) > 0,
      "v=%d c=%d po=%d" % (len(v_ids), len(c_ids), len(po_ids)))

# ---- State (Gujarat) test data ke liye ----
with app.app_context():
    guj = State.query.filter_by(name="Gujarat").first()
    guj_id = guj.id if guj else None
check("Gujarat state present", guj_id is not None)

# ---- Vendor list page: dropdown ab Payment Terms Master se ----
r = client.get("/vendors")
check("GET /vendors -> 200", r.status_code == 200, str(r.status_code))
check("vendors select name=payment_terms_id present", b'name="payment_terms_id"' in r.data)
check("vendors old select name=\"payment_terms\" gone", b'name="payment_terms"' not in r.data)
check("vendors dropdown option text = master name (Net 30)", b">Net 30</option>" in r.data)
check("vendors blank option present (Select terms)",
      b"Select terms" in r.data)

# ---- Customer list page ----
r = client.get("/customers")
check("GET /customers -> 200", r.status_code == 200, str(r.status_code))
check("customers select name=payment_terms_id present", b'name="payment_terms_id"' in r.data)
check("customers old select name=\"payment_terms\" gone", b'name="payment_terms"' not in r.data)
check("customers dropdown option = master name (Net 30)", b">Net 30</option>" in r.data)

# ---- Purchase order list page ----
r = client.get("/purchase_orders")
check("GET /purchase_orders -> 200", r.status_code == 200, str(r.status_code))
check("purchase_orders select name=payment_terms_id present", b'name="payment_terms_id"' in r.data)
check("purchase_orders old select name=\"payment_terms\" gone", b'name="payment_terms"' not in r.data)
check("purchase_orders dropdown option = master name (Net 30)", b">Net 30</option>" in r.data)

# ---- Vendor: add WITH terms id ----
r = client.post("/vendors/add", data={
    "code": V_CODE, "name": "PT FK Vendor", "state_id": str(guj_id),
    "payment_terms_id": str(net30_id),
    "opening_balance": "0", "opening_balance_type": "Cr",
}, follow_redirects=True)
check("vendor add-with-terms success", b"Vendor saved" in r.data, str(r.status_code))
with app.app_context():
    v = Vendor.query.filter_by(code=V_CODE).first()
    check("vendor stored with payment_terms_id", bool(v) and v.payment_terms_id == net30_id,
          str(v.payment_terms_id) if v else "none")
    check("vendor relationship -> Net 30",
          bool(v) and v.payment_terms is not None and v.payment_terms.name == "Net 30",
          v.payment_terms.name if v and v.payment_terms else "none")
    vid = v.id if v else None

# list me display (.name) aur edit data attribute (id) dono
r = client.get("/vendors")
check("vendors list shows terms name for vendor row", b"Net 30" in r.data)

# ---- Vendor: add WITHOUT terms (optional) ----
r = client.post("/vendors/add", data={
    "code": "VPTTEST2", "name": "No Terms Vendor", "state_id": str(guj_id),
    "opening_balance": "0", "opening_balance_type": "Cr",
}, follow_redirects=True)
check("vendor add-without-terms allowed", b"Vendor saved" in r.data)
with app.app_context():
    v2 = Vendor.query.filter_by(code="VPTTEST2").first()
    check("vendor optional terms stored NULL", bool(v2) and v2.payment_terms_id is None)
    v2id = v2.id if v2 else None

# ---- Vendor: add with INVALID terms id -> error ----
r = client.post("/vendors/add", data={
    "code": "VPTTEST3", "name": "Bad Terms Vendor", "state_id": str(guj_id),
    "payment_terms_id": "99999",
    "opening_balance": "0", "opening_balance_type": "Cr",
}, follow_redirects=True)
check("vendor invalid terms flashes error", b"valid payment terms" in r.data)
with app.app_context():
    check("invalid-terms vendor not created", Vendor.query.filter_by(code="VPTTEST3").first() is None)

# ---- Vendor: edit change terms Net 30 -> Net 15 ----
r = client.post("/vendors/edit/%d" % vid, data={
    "code": V_CODE, "name": "PT FK Vendor", "state_id": str(guj_id),
    "payment_terms_id": str(net15_id),
    "opening_balance": "0", "opening_balance_type": "Cr",
}, follow_redirects=True)
check("vendor edit flash success", b"Vendor Updated" in r.data)
with app.app_context():
    v = Vendor.query.get(vid)
    check("vendor edit changed terms id", v.payment_terms_id == net15_id, str(v.payment_terms_id))
    check("vendor edit relationship -> Net 15",
          v.payment_terms and v.payment_terms.name == "Net 15",
          v.payment_terms.name if v.payment_terms else "none")

# ---- Vendor: edit clear terms (optional) ----
client.post("/vendors/edit/%d" % vid, data={
    "code": V_CODE, "name": "PT FK Vendor", "state_id": str(guj_id),
    "opening_balance": "0", "opening_balance_type": "Cr",
}, follow_redirects=True)
with app.app_context():
    v = Vendor.query.get(vid)
    check("vendor edit can clear terms to NULL", v.payment_terms_id is None, str(v.payment_terms_id))

# ---- Customer: add WITH terms id ----
r = client.post("/customers/add", data={
    "code": C_CODE, "name": "PT FK Customer", "state_id": str(guj_id),
    "payment_terms_id": str(net30_id),
    "opening_balance": "0", "opening_balance_type": "Dr",
}, follow_redirects=True)
check("customer add-with-terms success", b"Customer saved" in r.data, str(r.status_code))
with app.app_context():
    c = Customer.query.filter_by(code=C_CODE).first()
    check("customer stored with payment_terms_id", bool(c) and c.payment_terms_id == net30_id,
          str(c.payment_terms_id) if c else "none")
    check("customer relationship -> Net 30",
          bool(c) and c.payment_terms is not None and c.payment_terms.name == "Net 30",
          c.payment_terms.name if c and c.payment_terms else "none")
    cid = c.id if c else None

# ---- Customer: add with INVALID terms -> error ----
r = client.post("/customers/add", data={
    "code": "CPTTEST2", "name": "Bad Terms Customer", "state_id": str(guj_id),
    "payment_terms_id": "99999",
    "opening_balance": "0", "opening_balance_type": "Dr",
}, follow_redirects=True)
check("customer invalid terms flashes error", b"valid payment terms" in r.data)
with app.app_context():
    check("invalid-terms customer not created", Customer.query.filter_by(code="CPTTEST2").first() is None)

# ---- Customer: edit change terms ----
r = client.post("/customers/edit/%d" % cid, data={
    "code": C_CODE, "name": "PT FK Customer", "state_id": str(guj_id),
    "payment_terms_id": str(net15_id),
    "opening_balance": "0", "opening_balance_type": "Dr",
}, follow_redirects=True)
with app.app_context():
    c = Customer.query.get(cid)
    check("customer edit changed terms id", c.payment_terms_id == net15_id, str(c.payment_terms_id))

# ---- Purchase Order: vendor auto-fill + add with terms ----
# Warehouse chain ensure karo (PO ko warehouse chahiye)
with app.app_context():
    wh = Warehouse.query.filter(Warehouse.is_deleted == False).first()
    made_wh = False
    if not wh:
        br = Branch(name=TMP_BR, state_id=guj_id, is_active=True, is_deleted=False)
        db.session.add(br)
        db.session.flush()
        wh = Warehouse(code=TMP_WH, name="PT Test Warehouse", warehouse_type="Main",
                       branch_id=br.id, location="Test", is_active=True, is_deleted=False)
        db.session.add(wh)
        db.session.commit()
        made_wh = True
    wh_id = wh.id
    # vendor ko wapas Net 30 do (auto-fill test ke liye)
    v = Vendor.query.get(vid)
    v.payment_terms_id = net30_id
    db.session.commit()

# vendor option me data-terms=<id> hona chahiye (JS auto-fill isi se karta hai)
r = client.get("/purchase_orders")
check("PO vendor option carries data-terms id (auto-fill source)",
      ('data-terms="%d"' % net30_id).encode() in r.data)

r = client.post("/purchase_orders/add", data={
    "vendor_id": str(vid), "warehouse_id": str(wh_id), "po_date": "2026-10-02",
    "payment_terms_id": str(net30_id), "remarks": "PT-FK-TEST",
}, follow_redirects=True)
check("PO add-with-terms success", b"Purchase Order" in r.data and b"saved" in r.data, str(r.status_code))
with app.app_context():
    po = PurchaseOrder.query.filter_by(remarks="PT-FK-TEST").order_by(PurchaseOrder.id.desc()).first()
    check("PO stored with payment_terms_id", bool(po) and po.payment_terms_id == net30_id,
          str(po.payment_terms_id) if po else "none")
    check("PO relationship -> Net 30",
          bool(po) and po.payment_terms is not None and po.payment_terms.name == "Net 30",
          po.payment_terms.name if po and po.payment_terms else "none")

# ---- Rename reflection: master rename turant list me dikhe ----
with app.app_context():
    tmp = PaymentTerm(code=TMP_PT, name="Temp PT For Verify", is_active=True, is_deleted=False)
    db.session.add(tmp)
    db.session.commit()
    tmp_id = tmp.id
    v = Vendor.query.get(vid)
    v.payment_terms_id = tmp_id
    db.session.commit()
with app.app_context():
    tmp = PaymentTerm.query.get(tmp_id)
    tmp.name = "Temp PT Renamed"
    db.session.commit()
r = client.get("/vendors")
check("vendor list reflects renamed master term", b"Temp PT Renamed" in r.data)

# ---- Soft-deleted term: reject + hidden from dropdown ----
with app.app_context():
    tmp = PaymentTerm.query.get(tmp_id)
    tmp.is_deleted = True
    db.session.commit()
r = client.post("/vendors/add", data={
    "code": "VPTTEST4", "name": "Deleted Terms Vendor", "state_id": str(guj_id),
    "payment_terms_id": str(tmp_id),
    "opening_balance": "0", "opening_balance_type": "Cr",
}, follow_redirects=True)
check("soft-deleted term flashes 'valid payment terms'", b"valid payment terms" in r.data)
with app.app_context():
    check("soft-deleted term vendor not created", Vendor.query.filter_by(code="VPTTEST4").first() is None)
r = client.get("/vendors")
check("soft-deleted term hidden from dropdown",
      ('<option value="%d">Temp PT Renamed</option>' % tmp_id).encode() not in r.data)

# ---- Cleanup ----
with app.app_context():
    cleanup()
    check("cleanup: test vendor gone", Vendor.query.filter_by(code=V_CODE).first() is None)
    check("cleanup: test customer gone", Customer.query.filter_by(code=C_CODE).first() is None)
    check("cleanup: test PO gone", PurchaseOrder.query.filter_by(remarks="PT-FK-TEST").first() is None)
    check("cleanup: temp term gone", PaymentTerm.query.filter_by(code=TMP_PT).first() is None)
    check("cleanup: master still 5 terms", PaymentTerm.query.count() == 5,
          str(PaymentTerm.query.count()))

for status, label, extra in results:
    print("%s - %s%s" % (status, label, " [" + extra + "]" if extra else ""))
print("TOTAL:", sum(1 for x in results if x[0] == "PASS"), "/", len(results))
