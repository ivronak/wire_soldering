# Ye file server start karne ke liye hai - isi ko "python run.py" se chalate hai
import os

# Local (debug on) par development key / non-Secure cookie chalti hai; live par ERP_DEBUG=0 + asli ERP_SECRET_KEY (flow doc 10.2).
# "app" import se PEHLE set karna zaroori hai, kyunki create_app import par hi chal jaata hai.
if os.environ.get("ERP_DEBUG", "1") == "1":
    os.environ.setdefault("ERP_DEV", "1")

from app import app

if __name__ == "__main__":
    # Debug mode sirf apne computer pe — isme error page pe code dikhta hai, server pe khatarnak hai.
    # VPS pe ERP_DEBUG=0 set karna (ya waha gunicorn/waitress jaisa proper server use karna).
    debug = os.environ.get("ERP_DEBUG", "1") == "1"
    app.run(debug=debug)
