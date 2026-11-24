# Phase 0 deploy: STAGING page sweep ab login ke saath (guard ke baad bina login har page 302 deta hai, isliye purana sweep fail hota).
# Use (server par, staging clone me, live DB ki COPY par):   python staging_sweep.py <staging_app_dir> [instance_dir_override]
# Ye staging DB copy me ek "Staging sweep" Developer banata hai (sirf copy me; live DB me kabhi nahi) aur uske session se saare GET pages kholta hai.
# Fail (exit 1) agar: koi page 5xx, Developer ko 401/403 / login-redirect mile, ya selfcheck (har URL rule guard_map me mapped) fail ho.
import os
import sys

APP_DIR = os.path.abspath(sys.argv[1])
INSTANCE = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.path.join(APP_DIR, "instance")
os.environ["ERP_DEV"] = "1"          # sirf staging copy: dev secret + non-Secure cookie (test client http par chale)
sys.path.insert(0, APP_DIR)

import flask


class _Flask(flask.Flask):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("instance_path", INSTANCE)
        super().__init__(*args, **kwargs)


flask.Flask = _Flask
from app import app                                               # noqa: E402
from app.auth import selfcheck                                    # noqa: E402
from app.auth.testing import login_client, make_user              # noqa: E402
from app.extensions import db                                     # noqa: E402
from app.models import PurchaseOrder, User                        # noqa: E402

with app.app_context():
    assert "stage" in str(db.engine.url).lower() or "costdemo" in str(db.engine.url).lower(), "ye staging DB nahi lagti: %s" % db.engine.url
    problems = selfcheck.problems(app)
    if problems:
        print("SELFCHECK FAILED:", problems[:10])
        sys.exit(1)
    dev = User.query.filter_by(mobile="9000000000").first() or make_user("Staging sweep", "9000000000", role="developer")
    dev_id = dev.id
    urls = sorted({r.rule for r in app.url_map.iter_rules() if "GET" in r.methods and not r.arguments and r.endpoint != "static"})
    urls += ["/grns?tab=completed", "/inward_qc?tab=completed", "/purchase_invoices?tab=completed", "/purchase_orders?tab=completed"]
    for po in PurchaseOrder.query.all():
        urls += ["/purchase_orders/%d/docket" % po.id, "/purchase_orders/%d/print" % po.id]
    db.session.remove()

with app.app_context():
    client = login_client(app, db.session.get(User, dev_id))
bad = []
urls = sorted(set(urls))
for url in urls:
    response = client.get(url)
    code = response.status_code
    location = response.headers.get("Location", "")
    if code >= 500 or code in (401, 403) or (code in (301, 302) and "/login" in location):
        bad.append((url, code, location))
print("staging pages tried:", len(urls), "bad:", bad)
sys.exit(1 if bad else 0)
