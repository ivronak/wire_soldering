# Phase 0: auth ka saara jodna ek jagah — app/__init__.py sirf 2 function bulata hai:
#   configure_security(app)  -> secret key, cookie flags, ProxyFix, DB timeout   (config, blueprints se pehle)
#   init_auth(app)           -> login manager, guard, CSRF, error pages, admin blueprints, CLI, template helpers (sab register hone ke baad)
# Guard CSRF se PEHLE register hota hai: anonymous POST ko CSRF error nahi, seedha login par bhejna hai.
import os
import secrets
import time

from flask import Response, g, jsonify, redirect, render_template, request, session, url_for
from flask_login import LoginManager
from flask_wtf.csrf import CSRFError, CSRFProtect, generate_csrf
from werkzeug.middleware.proxy_fix import ProxyFix

from app.auth import guard, guard_map, nav, registry as R, security, service
from app.auth.cli import register_cli
from app.extensions import db
from app.models import User

DEV_SECRET = "dev-wire-soldering-change-later"
MAX_SESSION_SECONDS = 30 * 24 * 3600     # safety net: 30 din se purani login cookie nahi chalti (idle logout nahi hai, user ka faisla)

login_manager = LoginManager()
csrf = CSRFProtect()


def configure_security(app):
    dev = os.environ.get("ERP_DEV") == "1"
    secret = os.environ.get("ERP_SECRET_KEY") or (DEV_SECRET if dev else "")
    problem = security.config_problem(secret, dev)
    app.config["ERP_DEV"] = dev
    app.config["AUTH_CONFIG_PROBLEM"] = problem
    # Problem ho to bhi koi random key do (CLI / migration chalte rahein); guard har web request ko 503 dega
    app.config["SECRET_KEY"] = secret if not problem else secrets.token_hex(32)
    if problem:
        print("SECURITY CONFIG ERROR: %s The web app will refuse all requests until this is fixed." % problem)

    app.config["SESSION_COOKIE_NAME"] = "wserp_session"          # portal ke parent domain par dusre apps ke cookie se alag
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = not dev                 # live par HTTPS-only; local http par chalna chahiye
    app.config["WTF_CSRF_TIME_LIMIT"] = None                      # khula tab 1 ghante baad bhi chale
    # SQLite: dusra worker likh raha ho to 15 second ruko (default 5) — login / audit write "database is locked" na de
    options = dict(app.config.get("SQLALCHEMY_ENGINE_OPTIONS") or {})
    options.setdefault("connect_args", {})["timeout"] = 15
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = options
    if not dev:
        # LiteSpeed / proxy ke peeche asli client IP, scheme aur host (lockout IP-wala hai, isliye zaroori)
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)


def _load_user(user_id):
    # Flask-Login har request par ise bulata hai. None = logged-out maano (cookie purani / user band / role band).
    try:
        user = db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None
    if user is None or not user.is_active:
        return None
    if session.get("sv") != user.session_version:           # password badla / reset / deactivate / role badla
        return None
    if time.time() - (session.get("lt") or 0) > MAX_SESSION_SECONDS:
        return None
    if user.role is None or not user.role.is_active:        # role band / hata = login band (Developer / Admin role kabhi band nahi hote)
        return None
    return user


def init_auth(app):
    login_manager.init_app(app)
    login_manager.user_loader(_load_user)
    login_manager.session_protection = "basic"
    login_manager.login_view = "auth.login"

    from app.auth.routes import auth_bp
    app.register_blueprint(auth_bp)

    app.before_request(guard.guard)             # pehle guard ...
    csrf.init_app(app)                          # ... phir CSRF (uska before_request baad me judta hai)
    app.after_request(guard.add_response_headers)

    @app.errorhandler(CSRFError)
    def csrf_failed(error):
        message = "Your page was open too long, or the form is no longer valid. Please reload the page and try again."
        if guard.wants_json():
            return jsonify(success=False, error=message), 400
        return render_template("auth/message.html", heading="Please try again", message=message), 400

    @app.errorhandler(403)
    def forbidden(error):
        return guard._forbidden(None)

    @app.context_processor
    def inject_auth():
        user = service.current()

        def can(key, level=R.LEVEL_VIEW):
            return user is not None and service.user_can(user, key, level)

        def can_edit(key):
            return can(key, R.LEVEL_EDIT)

        def can_any(*keys):
            return user is not None and service.user_can_any(user, keys)

        def can_do(endpoint, method="POST", party_type=None):
            # Template me button / link chhupane ke liye: "kya user ye URL (endpoint) khol / chala sakta hai?" — guard ke SAME rule se.
            # {% if can_do('production_orders.production_orders_release') %}<form ...>{% endif %}   (POST default)
            # {% if can_do('routing.routing_list', 'GET') %}<a href=...>{% endif %}
            # Vendor / customer documents: {% if can_do('party_documents.party_documents_add', 'POST', party_type='vendor') %}
            if user is None:
                return False
            rule = guard_map.resolve(endpoint, method)
            if rule is None:
                return False
            if rule.kind in ("public", "login"):
                return True
            if rule.kind == "developer":
                return user.kind == service.KIND_DEVELOPER
            keys = rule.keys
            if rule.kind == "party" and party_type in guard_map.PARTY_KEY:
                keys = (guard_map.PARTY_KEY[party_type],)       # vendor / customer document: guard jaisa hi ek key
            return service.user_can_any(user, keys, rule.level)

        # Sidebar ke drawers (module -> pages): sirf logged-in user ke dekhne layak pages (app/auth/nav.py)
        return {"can": can, "can_edit": can_edit, "can_any": can_any, "can_do": can_do, "me": user,
                "nav_modules": nav.build_nav(user), "csrf_token_value": generate_csrf}

    register_cli(app)

    from app.auth import admin_users, admin_roles, admin_access, admin_audit    # P0-7 screens
    app.register_blueprint(admin_users.admin_users_bp)
    app.register_blueprint(admin_roles.admin_roles_bp)
    app.register_blueprint(admin_access.admin_access_bp)
    app.register_blueprint(admin_audit.admin_audit_bp)
