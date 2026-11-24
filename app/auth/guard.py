# Phase 0 (P0-4): poore app ka ek hi darwaza. Har request pehle yahan se guzarti hai (before_request):
#   login hai? -> password badalna baaki? -> is URL ke page par user ka level kaafi hai? Nahi to 401 / redirect / 403.
# DENY-BY-DEFAULT: jo URL guard_map me nahi, wo band. Asli suraksha yahin hai — sidebar me link chhupana sirf suvidha hai.
# Related: app/auth/guard_map.py (kaun sa URL kis page ka), app/auth/service.py (user ke rights), app/auth/selfcheck.py (test).
from flask import (Response, current_app, g, jsonify, redirect, render_template, request, session, url_for)

from app.auth import guard_map
from app.auth import registry as R
from app.auth import service
from app.models import PartyDocument

PASSWORD_CHANGE_ALLOWED = {"auth.change_password", "auth.logout", "static"}


def wants_json(rule=None):
    # fetch / JS wale call ko HTML redirect nahi, JSON jawab chahiye. Header hamara apna fetch-wrapper lagata hai (csrf.js);
    # Accept header par bharosa nahi (browser form bhi "*/*" bhejta hai).
    if rule is not None and rule.json:
        return True
    return request.headers.get("X-Requested-With") == "fetch"


def _json_error(status, message, **extra):
    body = {"success": False, "error": message}
    body.update(extra)
    response = jsonify(body)
    response.status_code = status
    return response


def _unauthenticated(rule):
    if wants_json(rule):
        return _json_error(401, "Your session has ended. Please log in again.", login_url=url_for("auth.login"))
    if request.method == "GET":
        path = request.full_path.rstrip("?")
        return redirect(url_for("auth.login", next=path))
    return redirect(url_for("auth.login"))


def _forbidden(rule, message=None):
    message = message or "You do not have access to this page. Ask your administrator."
    if wants_json(rule):
        return _json_error(403, message)
    user = service.current()
    endpoint = service.first_permitted_endpoint(user) if user is not None else None
    first_page_url = url_for(endpoint) if endpoint else None
    return render_template("auth/forbidden.html", message=message, active_nav=None, first_page_url=first_page_url), 403


def _party_keys(rule):
    # vendor / customer document: kaun sa party hai us se key tay hoti hai (URL me party_type, ya document id se)
    party_type = (request.view_args or {}).get("party_type")
    if party_type is None and "doc_id" in (request.view_args or {}):
        doc = PartyDocument.query.get((request.view_args or {}).get("doc_id"))
        party_type = doc.party_type if doc else None
    key = guard_map.PARTY_KEY.get(party_type)
    return (key,) if key else rule.keys


def guard():
    # 1) server galat configured (secret key nahi) to koi bhi page nahi khulta
    if current_app.config.get("AUTH_CONFIG_PROBLEM"):
        return Response("This server is not configured securely. Please contact the administrator.", 503, mimetype="text/plain")

    endpoint = request.endpoint
    if endpoint is None:
        return None                                  # galat URL -> normal 404, kuch batata nahi
    rule = guard_map.resolve(endpoint, request.method)
    if rule is None:
        return _forbidden(None, "This page is not available.")     # map me nahi = deny
    if rule.kind == "public":
        return None

    user = service.current()
    if user is None:
        return _unauthenticated(rule)

    # Naya user / Admin reset ke baad pehle password badalna zaroori
    if user.must_change_password and endpoint not in PASSWORD_CHANGE_ALLOWED:
        if wants_json(rule):
            return _json_error(403, "Please change your password first.", change_password_url=url_for("auth.change_password"))
        return redirect(url_for("auth.change_password"))

    if rule.kind == "login":
        return None
    if rule.kind == "developer":
        allowed = user.kind == service.KIND_DEVELOPER
    elif rule.kind == "party":
        allowed = service.user_can_any(user, _party_keys(rule), rule.level)
    else:
        allowed = service.user_can_any(user, rule.keys, rule.level)
    if not allowed:
        return _forbidden(rule)
    return None


def add_response_headers(response):
    # Clickjacking / MIME-sniff se bachav; login ke baad ke pages cache nahi hote (shared PC par back-button se purana data nahi)
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    if request.endpoint != "static":
        response.headers["Cache-Control"] = "no-store, private"
        response.headers.add("Vary", "Cookie")
    return response
