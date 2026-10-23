# Live (portal) ERP ko demo / client ke liye "real jaisa" banata hai (2026-10-23, user ka kehna: test data hatao, masters saaf, 1-3 entry).
#   python live_data_reset.py <erp.db path> [uploads folder]
# 1) Test TRANSACTIONS hatata hai (PO, GRN, QC, bills, returns, production order, stock lots + movements) -> stock/ledger zero.
# 2) Masters me test junk ko soft-delete (is_deleted=1) karta hai, baaki ke naam / details real jaise karta hai.
# Hard delete sirf test transactions par (user ki permission se, pehle poora DB + uploads ka backup server par banta hai).
# Masters kabhi hard-delete nahi hote. Dobara chalane par bhi safe (idempotent).
import os
import shutil
import sqlite3
import sys

db_path = sys.argv[1]
uploads = sys.argv[2] if len(sys.argv) > 2 else None
c = sqlite3.connect(db_path)
c.execute("pragma foreign_keys=off")
tables = {r[0] for r in c.execute("select name from sqlite_master where type='table'")}


def run(sql, *args):
    cur = c.execute(sql, args)
    return cur.rowcount


# ------------------------------------------------------------------ 1) test transactions
tx_tables = [
    "rejection_memos", "inward_qc_results", "inward_qc", "grn_lines", "grns",
    "fg_movements", "fg_batches", "production_outputs", "production_order_stage_machines", "production_order_stages",
    "material_return_lines", "material_returns", "material_issue_lines", "material_issues",
    "stock_transfer_lines", "stock_transfers", "stock_adjustment_lines", "stock_adjustments", "opening_stock_lines", "opening_stocks",
    "stock_movements", "stock_lots",
    "purchase_return_charges", "purchase_return_lines", "purchase_returns",
    "purchase_invoice_charges", "purchase_invoice_lines", "purchase_invoices",
    "purchase_order_revisions", "purchase_order_charges", "purchase_order_lines", "purchase_orders",
    "production_order_lines", "production_orders",
]
for t in tx_tables:
    if t in tables:
        n = run(f'delete from "{t}"')
        if "sqlite_sequence" in tables:
            run("delete from sqlite_sequence where name=?", t)
        if n:
            print(f"  cleared {t}: {n}")

# party documents of removed test parties (vendor 1, customer 1)
run("delete from party_documents where (party_type='vendor' and party_id=1) or (party_type='customer' and party_id=1)")

# ledgers: opening / current balance zero (test balances), naam vendor / customer ke saath
run("update ledgers set opening_balance=0, current_balance=0")

# ------------------------------------------------------------------ 2) masters
# Vendors: test naam hatao (soft-delete), 3 real jaise rakho
run("update vendors set is_deleted=1 where code in ('V-0001','V-0002','V-0006','V-0008','V-0009')")
run("update vendors set name='Gujarat Flux & Chemicals Pvt Ltd', gstin='24AABCG4521K1Z3', email='sales@gujaratflux.in', contact_person='Nilesh Shah' where code='V-0004'")
run("update ledgers set name='Gujarat Flux & Chemicals Pvt Ltd', gstin='24AABCG4521K1Z3' where id=(select ledger_id from vendors where code='V-0004')")
# Customers: personal test customer hatao
run("update customers set is_deleted=1 where code='C-0001'")
# Product categories: sirf Soldering Wire rakho
run("update product_categories set is_deleted=1 where code in ('PC-0001','PC-0004')")
# Raw material categories: Sleeve hatao (PVC sleeving solder wire me nahi lagta)
run("update rm_categories set is_deleted=1 where code='RMC-0006'")
# Raw materials: test / faltu hatao, flux ka naam real
run("update raw_materials set is_deleted=1 where code in ('RM-0004','RM-0005','RM-0010','RM-0012','RM-0013')")
run("update raw_materials set name='Rosin Flux (Activated)' where code='RM-0011'")
# QC parameters: tin purity limit 100.5 galat tha; ingot par 'Gauge' test nahi lagta
run("update rm_qc_parameters set min_value=99.5 where raw_material_id=(select id from raw_materials where code='RM-0001') and name='Purity'")
run("update rm_qc_parameters set is_deleted=1 where name='Gauge' and raw_material_id in (select id from raw_materials where code in ('RM-0001','RM-0006'))")
# Product 11 ka naam saaf
run("update products set name='Soldering Wire 70/30 1.8mm 2.00%' where code='FG-0011'")
# Spelling: 'Alloye Grade' -> 'Alloy Grade' (kisi bhi text column me)
for t in tables:
    for col in [r[1] for r in c.execute(f'pragma table_info("{t}")') if "CHAR" in (r[2] or "").upper() or "TEXT" in (r[2] or "").upper() or (r[2] or "") == "JSON"]:
        n = run(f'update "{t}" set "{col}"=replace("{col}",\'Alloye Grade\',\'Alloy Grade\') where "{col}" like \'%Alloye Grade%\'')
        if n:
            print(f"  spelling fixed in {t}.{col}: {n}")

c.commit()

# ------------------------------------------------------------------ uploads (sirf test PO bills, QC reports, hataye gaye party ke documents)
if uploads and os.path.isdir(uploads):
    for sub in ("purchase_orders", "inward_qc", os.path.join("vendors", "1"), os.path.join("customers", "1")):
        path = os.path.join(uploads, sub)
        if os.path.isdir(path):
            shutil.rmtree(path)
            print("  removed uploads/" + sub)

c.execute("pragma foreign_keys=on")
print("integrity:", c.execute("pragma integrity_check").fetchone()[0], "| fk problems:", len(c.execute("pragma foreign_key_check").fetchall()))
for label, sql in [("vendors", "select code,name from vendors where is_deleted=0"), ("customers", "select code,name from customers where is_deleted=0"),
                   ("raw materials", "select code,name from raw_materials where is_deleted=0"), ("products", "select code,name from products where is_deleted=0"),
                   ("product categories", "select code,name from product_categories where is_deleted=0")]:
    print(label, c.execute(sql).fetchall())
