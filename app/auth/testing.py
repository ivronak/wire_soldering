# Phase 0: sirf TEST scripts ke liye — logged-in test client. Guard / CSRF ko bypass NAHI karta: asli session cookie + asli CSRF token.
# Use:
#   from app.auth.testing import make_user, login_client
#   client = login_client(app, user)           # user: User object (jaise Developer)
#   client.post("/units/add", data={...})      # CSRF token apne aap lagta hai
# Production code isse import nahi karta.
from flask.testing import FlaskClient

from app.auth import security
from app.extensions import db
from app.models import Role, User


class ErpTestClient(FlaskClient):
    # Har non-GET request me valid CSRF token header laga deta hai (token session ke raw token se banta hai)
    csrf_auto = True

    def open(self, *args, **kwargs):
        method = (kwargs.get("method") or "GET").upper()
        if self.csrf_auto and method not in ("GET", "HEAD", "OPTIONS"):
            headers = dict(kwargs.get("headers") or {})
            if "X-CSRFToken" not in headers:
                headers["X-CSRFToken"] = self.csrf_token()
            kwargs["headers"] = headers
        return super().open(*args, **kwargs)

    def csrf_token(self):
        # Flask-WTF jaisa hi token: session me raw token rakho, aur secret-key se signed version header me bhejo
        import hashlib
        import os

        from itsdangerous import URLSafeTimedSerializer
        with self.session_transaction() as sess:
            raw = sess.get("csrf_token")
            if not raw:
                raw = hashlib.sha1(os.urandom(64)).hexdigest()
                sess["csrf_token"] = raw
        serializer = URLSafeTimedSerializer(self.application.config["SECRET_KEY"], salt="wtf-csrf-token")
        return serializer.dumps(raw)


def make_user(full_name, mobile, password="TestPass-12345", role=None, must_change=False):
    # role: Role object, ya "developer" / "admin" (built-in roles ka system_key). Role dena zaroori hai.
    if isinstance(role, str):
        role = Role.query.filter_by(system_key=role).one()
    user = User(full_name=full_name, mobile=mobile, password_hash=security.hash_password(password),
                role_id=role.id, must_change_password=must_change)
    db.session.add(user)
    db.session.commit()
    return user


def login_client(app, user):
    # Seedha session me user daalte hain (login form / lockout ke bina) — taaki purani test scripts logged-in chal sakein
    import time
    app.test_client_class = ErpTestClient
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["_fresh"] = True
        sess["sv"] = user.session_version
        sess["lt"] = int(time.time())
    return client
