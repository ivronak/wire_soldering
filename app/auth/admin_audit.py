# Phase 0 (P0-7): Audit log — sirf Developer (guard_map: admin_audit blueprint developer-only). Sirf padhna, koi edit / delete nahi.
# Log me poora mobile number kabhi nahi hota (sirf aakhri 4 digit) — service.audit / login routes yehi karte hain.
import json
from datetime import datetime, timedelta

from flask import Blueprint, render_template, request
from sqlalchemy import or_

from app.extensions import db
from app.models import AuditLog

admin_audit_bp = Blueprint("admin_audit", __name__, url_prefix="/admin/audit", template_folder="templates")

PER_PAGE = 50
IST_OFFSET = timedelta(hours=5, minutes=30)


def _parse_day(text):
    try:
        return datetime.strptime(text, "%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def _pretty(detail):
    # detail JSON ho to "key: value" lines, warna jaisa hai waisa
    if not detail:
        return ""
    try:
        data = json.loads(detail)
    except ValueError:
        return detail
    if isinstance(data, dict):
        return "; ".join("%s: %s" % (k, json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v) for k, v in data.items())
    return str(data)


@admin_audit_bp.route("/")
def audit_page():
    action = (request.args.get("action") or "").strip()
    q = (request.args.get("q") or "").strip()
    start, end = _parse_day(request.args.get("from")), _parse_day(request.args.get("to"))
    query = AuditLog.query
    if action:
        query = query.filter(AuditLog.action == action)
    if q:
        like = "%" + q + "%"
        query = query.filter(or_(AuditLog.actor_label.ilike(like), AuditLog.detail.ilike(like), AuditLog.target_type.ilike(like)))
    # Date filter India (IST) din ke hisaab se; DB me UTC hai
    try:
        if start:
            query = query.filter(AuditLog.at >= start - IST_OFFSET)
        if end:
            query = query.filter(AuditLog.at < end + timedelta(days=1) - IST_OFFSET)
    except OverflowError:                     # 0001-01-01 / 9999-12-31 jaisi bahar ki tareekh: filter chhod do (500 nahi)
        pass
    total = query.count()
    pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    try:
        page = min(max(1, int(request.args.get("page") or 1)), pages)
    except ValueError:
        page = 1
    rows = query.order_by(AuditLog.id.desc()).offset((page - 1) * PER_PAGE).limit(PER_PAGE).all()
    actions = [a for (a,) in db.session.query(AuditLog.action).distinct().order_by(AuditLog.action).all()]
    entries = [{"row": r, "detail": _pretty(r.detail)} for r in rows]
    args = {k: v for k, v in (("action", action), ("q", q), ("from", request.args.get("from") or ""), ("to", request.args.get("to") or "")) if v}
    return render_template("admin/audit.html", entries=entries, actions=actions, action=action, q=q, date_from=args.get("from", ""),
                           date_to=args.get("to", ""), page=page, pages=pages, total=total, args=args, active_nav="audit_log")
