# Auth demo (/auth_demo) ka ટેસ્ટ ડેટા hatata hai taaki demo dobara saaf shuru ho:
#   - demo users (mobile 9876500002 / 03 / 04), roles "Store Keeper" aur "Production Viewer" (+ unke permissions)
#   - Admin ceiling (admin_ceiling) saaf, login_attempts (lockout) saaf
# Audit log ko NAHI chhuta (audit trail kabhi delete nahi hoti). Developer aur baaki asli users / roles ko bhi nahi chhuta.
#   venv/Scripts/python.exe scripts/auth_demo_reset.py [path/to/erp.db]      (default instance/erp.db — sirf LOCAL DB par chalao)
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "instance", "erp.db")
DEMO_MOBILES = ("9876500002", "9876500003", "9876500004", "9876500005", "9876500006")   # 05 = "test" role wala demo user, 06 = Suresh Desai (form demo)
DEMO_ROLES = ("Store Keeper", "Production Viewer")

con = sqlite3.connect(DB)
marks = ",".join("?" * len(DEMO_MOBILES))
users = con.execute(f"delete from users where mobile in ({marks})", DEMO_MOBILES).rowcount
rmarks = ",".join("?" * len(DEMO_ROLES))
role_ids = [r[0] for r in con.execute(f"select id from roles where system_key is null and name in ({rmarks})", DEMO_ROLES)]
for rid in role_ids:
    con.execute("delete from role_permissions where role_id=?", (rid,))
    con.execute("delete from roles where id=?", (rid,))
ceiling = con.execute("delete from admin_ceiling").rowcount
attempts = con.execute("delete from login_attempts").rowcount
con.commit()
con.close()
print(f"Demo reset on {DB}: {users} user(s), {len(role_ids)} role(s), {ceiling} ceiling row(s), {attempts} lockout row(s) removed.")
