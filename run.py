# Ye file server start karne ke liye hai - isi ko "python run.py" se chalate hai
import os

from app import app

if __name__ == "__main__":
    # Debug mode sirf apne computer pe — isme error page pe code dikhta hai, server pe khatarnak hai.
    # VPS pe ERP_DEBUG=0 set karna (ya waha gunicorn/waitress jaisa proper server use karna).
    debug = os.environ.get("ERP_DEBUG", "1") == "1"
    app.run(debug=debug)
