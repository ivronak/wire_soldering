import _guard  # Safety: asli erp.db pe chalti hai — bina ERP_ALLOW_DB_SCRIPTS=1 ke ruk jaayegi (dekho _guard.py)
# Sidebar grouping verify — base.html me grouped masters sahi render ho rahe hain ya nahi.
# Har sidebar endpoint ka url_for resolve karta hai aur page GET karke status check karta hai
# (har page base.html extend karta hai, isliye base.html ka Jinja compile bhi test hota hai).
import sys

from app import create_app

ENDPOINTS = [
    # Common
    "units.units_list",
    "tax_rates.tax_rates_list",
    "charges.charges_list",
    "states.states_list",
    "payment_terms.payment_terms_list",
    # Production
    "work_stages.work_stages_list",
    "machines.machines_list",
    # Raw material
    "rm_categories.rm_categories_list",
    "raw_materials.raw_materials_list",
    # Products
    "product_categories.product_categories_list",
    "products.products_list",
    # Storage
    "warehouses.warehouses_list",
    # Partners
    "vendors.vendors_list",
    "vendor_types.vendor_types_list",
    "customers.customers_list",
    # Other sections (sanity)
    "purchase_orders.purchase_orders_list",
    "grns.grns_list",
    "inward_qc.inward_qc_list",
    "production_orders.production_orders_list",
]

app = create_app()

passed = 0
total = 0
with app.test_request_context():
    from flask import url_for
    paths = []
    for ep in ENDPOINTS:
        total += 1
        try:
            paths.append((ep, url_for(ep)))
            passed += 1
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL url_for {ep}: {exc}")

client = app.test_client()
for ep, path in paths:
    total += 1
    resp = client.get(path)
    ok = resp.status_code == 200
    if ok:
        passed += 1
    print(f"{'PASS' if ok else 'FAIL'} GET {path} [{ep}] -> {resp.status_code}")

print(f"\n{passed}/{total} PASS")
sys.exit(0 if passed == total else 1)
