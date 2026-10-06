# Safety guard — scratchpad ki saari verify/renumber scripts isko sabse pehle import karti hain.
#
# Kyun: yeh scripts asli instance/erp.db pe chalti hain (test client se data add/edit/delete karti hain,
# kuch to poori table bhi saaf karti hain, jaise Charge.query.delete()). Galti se dobara chal gayi
# to real master data ud sakta hai. Isliye ab yeh tabhi chalengi jab tum jaan-boojhkar
# ERP_ALLOW_DB_SCRIPTS=1 set karo — aur chalne se pehle DB ka ek backup copy apne aap ban jaata hai.
#
# PowerShell me chalane ka tareeka:
#   $env:ERP_ALLOW_DB_SCRIPTS = "1"; $env:PYTHONPATH = "."; venv\Scripts\python.exe scratchpad\<script>.py
import os
import shutil
import sys
from datetime import datetime

if os.environ.get("ERP_ALLOW_DB_SCRIPTS") != "1":
    sys.exit(
        "STOPPED: this script writes to the REAL database (instance/erp.db).\n"
        "If you really want to run it, set ERP_ALLOW_DB_SCRIPTS=1 first "
        "(a backup of erp.db is made automatically before it runs)."
    )

# Chalne se pehle backup — kuch galat ho to yeh file wapas erp.db ki jagah copy kar dena
_db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "instance", "erp.db")
if os.path.exists(_db_path):
    _backup = _db_path + ".before-script-" + datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(_db_path, _backup)
    print("DB backup saved:", _backup)
