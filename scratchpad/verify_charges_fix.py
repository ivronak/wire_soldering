import _guard  # Safety: asli erp.db pe chalti hai — bina ERP_ALLOW_DB_SCRIPTS=1 ke ruk jaayegi (dekho _guard.py)
"""Charges-side fixes ka quick check.

Kya verify karta hai:
1. GET /charges 200 + sidebar link highlight (active_nav='charges' -> aria-current)
2. add normal (auto code CHG-0001)
3. restore branch - wahi path jahan `db.commit.session()` typo tha
4. edit me missing name crash na kare + normal edit chale

Restore branch normally HTTP se trigger nahi hoti kyunki
`generate_next_charge_code()` = `max(id) + 1` deta hai, jo existing code se
kabhi collide nahi karta. Isliye test me ek aisa row banaya jaata hai jiska
`code` agle generated code se match kare (id=5 par code='CHG-0006').

Ant me sirf apne banaye test rows delete karta hai (table khaali ho jaata hai).
"""
import re

from app import create_app
from app.extensions import db
from app.models import Charge

app = create_app()
client = app.test_client()


def body(resp):
    return resp.get_data(as_text=True)


def h1(resp):
    m = re.search(r"<h1[^>]*>(.*?)</h1>", body(resp), re.S)
    return " ".join(m.group(1).split()) if m else "(no h1)"


print("=== Charges fix verification ===")

# 0. Clean slate - pehle ke test rows hata do
with app.app_context():
    Charge.query.delete()
    db.session.commit()

# 1. List page + sidebar highlight
r = client.get("/charges")
print("GET /charges ->", r.status_code, "| heading:", h1(r))
print("   sidebar highlight (aria-current):", "aria-current" in body(r))

# 2. Normal add
r = client.post("/charges/add", data={"name": "Freight"}, follow_redirects=True)
with app.app_context():
    c = Charge.query.order_by(Charge.id.desc()).first()
    print("add ->", c.code, "|", c.name, "| active:", c.is_active, "| deleted:", c.is_deleted)

# 3. Restore branch (typo path)
#    Contrived row: id = max, par code = agla generated code -> collision -> restore branch
with app.app_context():
    Charge.query.delete()
    db.session.commit()
    db.session.add(Charge(id=5, code="CHG-0006", name="Old Deleted", is_active=False, is_deleted=True))
    db.session.commit()
    print("craft -> max id:", Charge.query.order_by(Charge.id.desc()).first().id,
          "| next code:", "CHG-0006 (collides with deleted row)")

r = client.post("/charges/add", data={"name": "Freight Restored"}, follow_redirects=True)
restore_flash = "restored" in body(r).lower()
with app.app_context():
    row = Charge.query.filter_by(code="CHG-0006").first()
    print("restore flash:", restore_flash)
    print("restore ->", row.code, "|", row.name, "| deleted:", row.is_deleted, "| active:", row.is_active)
    row_id = row.id

# 4. Edit - missing name should not crash
r = client.post(f"/charges/edit/{row_id}", data={}, follow_redirects=True)
print("edit with no name -> status:", r.status_code)

r = client.post(f"/charges/edit/{row_id}", data={"name": "Freight Fixed"}, follow_redirects=True)
with app.app_context():
    row = Charge.query.filter_by(code="CHG-0006").first()
    print("edit -> name now:", row.name)

# 5. Cleanup
with app.app_context():
    Charge.query.delete()
    db.session.commit()
    print("cleanup -> remaining charges rows:", Charge.query.count())

print("=== done ===")
