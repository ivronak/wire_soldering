# Phase 0 (P0-3): login, logout, change-password ke routes. Blueprint "auth" (koi url_prefix nahi: /login, /logout, /change-password).
# Login sirf MOBILE NUMBER + password se (flow doc 11.2). Sab galat-login ek hi message deta hai, taaki number ke baare me kuch pata na chale.
# Related: app/auth/lockout.py (galat password ginti), app/auth/service.py (audit, permission), app/auth/guard.py.
import time
from urllib.parse import urlparse

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import login_user, logout_user
from werkzeug.exceptions import HTTPException

from app.auth import guard_map, lockout, security, service
from app.extensions import db
from app.models import User
from app.timeutil import utc_now

auth_bp = Blueprint("auth", __name__, template_folder="templates")

GENERIC_FAIL = "Invalid mobile number or password."
INACTIVE_MSG = "This account is not active. Please contact your administrator."


def safe_next(user, target):
    # Login ke baad kahan jaana hai: sirf apni site ka relative path, jo GET se chalta ho aur user ke rights me ho
    if not target or not target.startswith("/") or target.startswith("//") or "\\" in target:
        return None
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in target):      # CR / LF jaise control character (redirect header toot jata)
        return None
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc:
        return None
    try:
        adapter = current_app.url_map.bind("localhost")
        endpoint, _args = adapter.match(parsed.path, method="GET")
    except HTTPException:
        return None
    if endpoint == "auth.login":
        return None                             # login page par hi wapas bhejne se loop banta hai
    rule = guard_map.resolve(endpoint, "GET")
    if rule is None:
        return None
    if rule.kind in ("public", "login"):
        return target
    if rule.kind == "developer":
        return target if user.kind == service.KIND_DEVELOPER else None
    return target if service.user_can_any(user, rule.keys, rule.level) else None


def _login_destination(user, target):
    safe = safe_next(user, target)
    if safe:
        return safe
    endpoint = service.first_permitted_endpoint(user)
    return url_for(endpoint) if endpoint else url_for("home")


def _start_session(user):
    # Naya session: purani session cookie ka kuch nahi rakhte (session fixation se bachav)
    session.clear()
    login_user(user, remember=False)
    session["sv"] = user.session_version
    session["lt"] = int(time.time())


def _locked_response(wait, raw_mobile, next_url):
    # Lock ke dauran har request ka audit row nahi likhte (bot se audit bhar jata) — lock lagne wala event pehle hi likha ja chuka.
    # Message sab ke liye ek jaisa (number / IP / Developer — kuch pata na chale)
    minutes = max(1, (wait + 59) // 60)
    return render_template("auth/login.html", error="Too many attempts. Please try again in %d minute%s." % (minutes, "" if minutes == 1 else "s"),
                           mobile=raw_mobile, next_url=next_url), 429


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    user = service.current()
    if request.method == "GET":
        if user is not None:
            if user.must_change_password:
                return redirect(url_for("auth.change_password"))
            return redirect(_login_destination(user, request.args.get("next")))
        return render_template("auth/login.html", error=None, mobile="", next_url=request.args.get("next") or "")

    raw_mobile = (request.form.get("mobile") or "").strip()
    password = request.form.get("password") or ""
    next_url = request.form.get("next") or ""
    mobile = security.normalize_mobile(raw_mobile)
    key = mobile or "invalid-format"            # galat format par bhi ginti chalti hai; sab junk ek hi key (table me row-spam nahi)
    ip = security.client_ip()

    # Pehle IP-wide lock (ek IP se bahut saari galat koshish — alag-alag numbers badal ke guess) aur us number ka lock: dono hash se PEHLE (sasta check)
    wait = max(lockout.seconds_locked(lockout.IP_KEY, ip), lockout.seconds_locked(key, ip))
    if wait:
        return _locked_response(wait, raw_mobile, next_url)
    # Koshish verify se PEHLE atomic gin lo (+1): warna ek saath aayi bahut si requests 5 se zyada password check kar leti (review 23 Nov).
    # 5vi koshish tak verify hoti hai; usse upar wali ko seedha lock jawab, password check nahi.
    attempt = lockout.register_failure(key, ip)
    if attempt > lockout.MAX_FAILS:
        return _locked_response(lockout.seconds_locked(key, ip) or lockout.LOCK_MINUTES * 60, raw_mobile, next_url)

    account = User.query.filter_by(mobile=mobile).first() if mobile else None
    # Unknown number par bhi ek asli hash check — jawab ka time same rahe
    password_ok = security.verify_password(account.password_hash if account else security.dummy_hash(), password)

    if account is not None and password_ok:
        lockout.clear(key, ip)                  # sahi password: reserve ki hui koshish wapas (inactive account par bhi — password to sahi tha)
        role_ok = account.role is not None and account.role.is_active
        if not account.is_active or not role_ok:
            service.audit("login_inactive", target_type="user", target_id=account.id, actor=account)
            db.session.commit()
            return render_template("auth/login.html", error=INACTIVE_MSG, mobile=raw_mobile, next_url=next_url), 403
        _start_session(account)
        account.last_login_at = utc_now()
        service.audit("login_ok", target_type="user", target_id=account.id, actor=account)
        db.session.commit()
        if account.must_change_password:
            return redirect(url_for("auth.change_password"))
        return redirect(_login_destination(account, next_url))

    # Galat password: IP-wide ginti bhi +1. Audit sirf kam baar: asli account ki pehli / lock wali koshish, ya unknown number par IP ki pehli 5 / lock wali koshish
    # (random numbers ki bauchhar se audit_log aur login_attempts table bhar na jaye — review 23 Nov)
    ip_count = lockout.register_failure(lockout.IP_KEY, ip, lockout.IP_MAX_FAILS)
    if account is not None:
        should_audit = attempt in (1, lockout.MAX_FAILS)
        locked_now = attempt >= lockout.MAX_FAILS
    else:
        should_audit = ip_count <= 5 or ip_count == lockout.IP_MAX_FAILS      # unknown number: IP ki pehli 5 + lock wali koshish (itna hi audit — spam nahi)
        locked_now = ip_count >= lockout.IP_MAX_FAILS
    if should_audit:
        service.audit("login_failed", target_type="user" if account else None, target_id=account.id if account else None,
                      label="unknown (%s)" % security.mask_mobile(mobile or raw_mobile), detail="locked" if locked_now else None)
    db.session.commit()
    return render_template("auth/login.html", error=GENERIC_FAIL, mobile=raw_mobile, next_url=next_url), 401


@auth_bp.route("/logout", methods=["POST"])
def logout():
    user = service.current()
    if user is not None:
        user.session_version += 1               # purani cookie (copy hui ho to bhi) ab bekaar; baaki devices bhi logout
        service.audit("logout", target_type="user", target_id=user.id, actor=user)
        db.session.commit()
    logout_user()
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/change-password", methods=["GET", "POST"])
def change_password():
    user = service.current()
    forced = user.must_change_password
    layout = "auth/plain.html" if forced else "base.html"
    if request.method == "GET":
        return render_template("auth/change_password.html", layout=layout, forced=forced, error=None, active_nav=None)

    current_pw = request.form.get("current_password") or ""
    new_pw = request.form.get("new_password") or ""
    confirm = request.form.get("confirm_password") or ""
    error = None
    ip = security.client_ip()
    pw_key = "pw:" + user.mobile                # change-password ke galat "current password" par bhi login jaisa lock
    if lockout.seconds_locked(pw_key, ip):
        return render_template("auth/change_password.html", layout=layout, forced=forced, error="Too many attempts. Please try again later.", active_nav=None), 429
    if not security.verify_password(user.password_hash, current_pw):
        error = "Current password is not correct."
        count = lockout.register_failure(pw_key, ip)
        if count in (1, lockout.MAX_FAILS):
            service.audit("password_change_failed", target_type="user", target_id=user.id, actor=user, detail="locked" if count >= lockout.MAX_FAILS else None)
            db.session.commit()
    elif new_pw != confirm:
        error = "New password and confirmation do not match."
    elif new_pw == current_pw:
        error = "New password must be different from the current one."
    else:
        error = security.password_problem(new_pw, user.mobile)
    if error:
        return render_template("auth/change_password.html", layout=layout, forced=forced, error=error, active_nav=None), 400

    lockout.clear(pw_key, ip)
    user.password_hash = security.hash_password(new_pw)
    user.must_change_password = False
    user.session_version += 1                   # baaki sab jagah ke purane session band
    service.audit("password_changed", target_type="user", target_id=user.id, actor=user)
    db.session.commit()
    session["sv"] = user.session_version         # is browser ka session chalta rahe
    flash("Password changed.", "success")
    return redirect(_login_destination(user, None))
