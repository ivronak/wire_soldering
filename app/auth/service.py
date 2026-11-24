# Phase 0: permission + user-management ka dimaag. Guard, template helper, admin screens aur CLI sab yahin ke functions use karte hain.
# User ka koi alag "type" nahi, sirf Role. Do built-in (system) roles: Developer (sab kuch) aur Admin (Developer ke diye ceiling ke pages);
# baaki custom roles (Admin banata hai) ke rights unke apne pages, jo ceiling ke andar clamp hote hain. user.kind = role se nikla read-only label.
# Tables: users, roles, role_permissions, admin_ceiling, audit_log (app/models.py). Pages ki list: app/auth/registry.py.
import json

from flask import g, has_request_context, request
from flask_login import current_user
from sqlalchemy import or_

from app.auth import registry as R
from app.auth.security import client_ip, mask_mobile
from app.extensions import db
from app.models import AdminCeiling, AuditLog, Role, User

KIND_DEVELOPER = "developer"      # = Role.system_key of the Developer role
KIND_ADMIN = "admin"              # = Role.system_key of the Admin role
KIND_STAFF = "staff"              # = koi custom role (system_key NULL)

# Admin ko Users / Roles pages hamesha milte hain (ceiling table me nahi rakhte)
IMPLICIT_ADMIN_KEYS = ("users", "roles")
MANAGER_KEYS = ("users", "roles")


# ---------- current user ----------

def current():
    # Logged-in User ya None (anonymous)
    if not has_request_context():
        return None
    user = current_user._get_current_object()
    return user if getattr(user, "is_authenticated", False) else None


# ---------- permissions ----------

def ceiling_map():
    # {key: level} — Admin kitna kar sakta hai (Developer ka diya). Staff roles bhi runtime par isi ke andar clamp hote hain.
    cached = getattr(g, "_ceiling_map", None) if has_request_context() else None
    if cached is not None:
        return cached
    result = {}
    for row in AdminCeiling.query.all():
        if R.get(row.page_key) and row.page_key not in R.DEVELOPER_ONLY_KEYS:
            result[row.page_key] = row.level
    for key in IMPLICIT_ADMIN_KEYS:
        result[key] = R.LEVEL_EDIT
    if has_request_context():
        g._ceiling_map = result
    return result


def _role_map(role, ignore_active=False):
    # {key: level} us role ke (valid) rows; Developer-only keys kabhi nahi. Inactive role ke rows runtime par 0 gine jaate hain,
    # par rank check (kaun kisko manage kare) ke liye asli rows chahiye — warna band role ka rank "khaali" dikhta (audit 23 Nov)
    if role is None or (not role.is_active and not ignore_active):
        return {}
    result = {}
    for perm in role.permissions:
        if R.get(perm.page_key) and perm.page_key not in R.DEVELOPER_ONLY_KEYS:
            result[perm.page_key] = perm.level
    return result


def permissions_of(user):
    # {key: level} — user ke sach me kitne rights hain (har request par DB se, request ke andar cache)
    if user is None:
        return {}
    cache = getattr(g, "_perm_cache", None) if has_request_context() else None
    if cache is not None and cache[0] == user.id:
        return cache[1]
    if user.kind == KIND_DEVELOPER:
        perms = {key: R.LEVEL_EDIT for key in R.all_keys()}
    elif user.kind == KIND_ADMIN:
        perms = dict(ceiling_map())
    else:
        ceiling = ceiling_map()
        perms = {}
        for key, level in _role_map(user.role).items():
            allowed = ceiling.get(key, 0)
            if allowed:
                perms[key] = min(level, allowed)
    if has_request_context():
        g._perm_cache = (user.id, perms)
    return perms


def level_of(user, key):
    return permissions_of(user).get(key, 0)


def user_can(user, key, level=R.LEVEL_VIEW):
    return user is not None and level_of(user, key) >= level


def user_can_any(user, keys, level=R.LEVEL_VIEW):
    return any(user_can(user, key, level) for key in keys)


def first_permitted_endpoint(user):
    # Login ke baad / home par kahan jaana hai: sidebar ke order me pehla page jo user dekh sakta hai (nahi mila to None)
    perms = permissions_of(user)
    for page in R.PAGES:
        if perms.get(page["key"], 0) >= R.LEVEL_VIEW:
            return page["endpoint"]
    return None


# ---------- rank rules (Admin ceiling bypass roakne ke liye — flow doc 10.1 + 11.1) ----------

def _within(perms_of_target, perms_of_actor):
    # target ka har key + level actor ke andar hona chahiye
    return all(perms_of_actor.get(key, 0) >= level for key, level in perms_of_target.items())


def role_within_actor(actor, role):
    # Kya is role ke saare (asli, ceiling ke andar wale) rights actor ke apne rights ke andar hain?
    # Ceiling se upar wali rows runtime par chalti hi nahi, isliye unhe gino nahi — warna Developer ceiling ghatate hi Admin us role ke users ko sambhal na pata.
    ceiling = ceiling_map()
    effective = {}
    for key, level in _role_map(role, ignore_active=True).items():
        level = min(level, ceiling.get(key, 0))
        if level:
            effective[key] = level
    return _within(effective, permissions_of(actor))


def is_manager_staff(actor):
    return actor is not None and actor.kind == KIND_STAFF


def role_violates_manager_rule(actor, role):
    # Manager-staff kisi ko aisa role nahi de sakta jisme users / roles page ho (power-chain lambi na ho)
    if not is_manager_staff(actor):
        return False
    return any(key in MANAGER_KEYS for key in _role_map(role, ignore_active=True))


def can_manage_user(actor, target):
    # Actor target user ko dekh / badal / reset / unlock / deactivate kar sakta hai?
    if actor is None or target is None or actor.id == target.id:
        return False
    if actor.kind == KIND_DEVELOPER:
        return target.kind != KIND_DEVELOPER
    if target.kind != KIND_STAFF:
        return False       # Admin / Manager-staff sirf Staff ko; Admin / Developer unhe dikhte hi nahi (visible_users_query)
    return role_within_actor(actor, target.role)


def can_assign_role(actor, role):
    if role is None or not role.is_active:
        return False
    if role.system_key == KIND_DEVELOPER:
        return False                      # Developer role kisi ko UI se nahi milta — sirf server command (flask create-developer)
    if role.system_key == KIND_ADMIN:
        return actor.kind == KIND_DEVELOPER   # Admin sirf Developer banata hai (user ka faisla 23 Nov)
    if actor.kind == KIND_DEVELOPER:
        return True
    return role_within_actor(actor, role) and not role_violates_manager_rule(actor, role)


def assignable_roles(actor):
    # Admin role pehle, phir baaki naam ke hisaab se
    roles = [role for role in Role.query.filter_by(is_active=True).all() if can_assign_role(actor, role)]
    return sorted(roles, key=lambda r: (r.system_key is None, r.name.lower()))


def validate_role_permissions(actor, requested, whole=None):
    # requested = {key: level}. Wapas: galtiyon ki list (khaali = theek). Server hi final faisla karta hai, UI sirf madad.
    # whole = role ki poori nayi map (jab requested sirf badli hui keys hon) — special permission ke "page bhi chahiye" check ke liye.
    whole = requested if whole is None else whole
    problems = []
    actor_perms = permissions_of(actor)
    for key, level in requested.items():
        page = R.get(key)
        if page is None:
            problems.append("Unknown permission: %s" % key)
            continue
        if key in R.DEVELOPER_ONLY_KEYS:
            problems.append("%s cannot be given to a role." % page["label"])
            continue
        if level not in (R.LEVEL_VIEW, R.LEVEL_EDIT) or (page["kind"] == "special" and level != R.LEVEL_EDIT):
            problems.append("Invalid level for %s." % page["label"])
            continue
        if page["kind"] == "special" and whole.get(page["page"], 0) < R.LEVEL_VIEW:
            problems.append("%s needs access to the %s page as well." % (page["label"], R.get(page["page"])["label"]))
            continue
        if actor.kind == KIND_DEVELOPER:
            continue
        if key in MANAGER_KEYS and actor.kind != KIND_ADMIN:
            problems.append("Only an Admin can give the %s page to a role." % page["label"])
            continue
        if actor_perms.get(key, 0) < level:
            problems.append("%s is not available for your account." % page["label"])
    return problems


def visible_users_query(actor):
    # Developer sirf Developer ko dikhta hai; Manager-staff sirf Staff dekhta hai. Har user list / count / dropdown isi se.
    query = User.query.join(Role, User.role_id == Role.id)
    if actor.kind == KIND_DEVELOPER:
        return query
    if actor.kind == KIND_ADMIN:
        return query.filter(or_(Role.system_key.is_(None), Role.system_key != KIND_DEVELOPER))
    return query.filter(Role.system_key.is_(None))


MAX_DB_ID = 2 ** 31 - 1


def parse_id(raw):
    # Form / URL se aayi id ko safe int me badalta hai (unicode digit "²", bahut bada number -> None, 500 nahi)
    text = (raw or "").strip() if isinstance(raw, str) else raw
    if isinstance(text, str):
        if not (text.isascii() and text.isdigit()) or len(text) > 10:
            return None
        text = int(text)
    if not isinstance(text, int) or not 0 < text <= MAX_DB_ID:
        return None
    return text


def get_visible_user(actor, user_id):
    if parse_id(user_id) is None:
        return None
    return visible_users_query(actor).filter(User.id == user_id).first()


# ---------- audit ----------

def audit_label(user):
    return "%s (%s)" % (user.full_name, mask_mobile(user.mobile)) if user is not None else None


def audit(action, target_type=None, target_id=None, detail=None, actor=None, label=None):
    # Ek audit row session me jodta hai (commit caller karta hai, taaki kaam + audit saath save hon / saath rollback hon)
    actor = actor if actor is not None else current()
    request_ok = has_request_context()
    row = AuditLog(
        action=action,
        actor_user_id=actor.id if actor is not None else None,
        actor_label=label or audit_label(actor),
        target_type=target_type,
        target_id=target_id,
        detail=detail if (detail is None or isinstance(detail, str)) else json.dumps(detail, sort_keys=True),
        ip=client_ip() if request_ok else None,
        user_agent=(request.headers.get("User-Agent") or "")[:200] if request_ok else None,
    )
    db.session.add(row)
    return row


# ---------- helpers for screens / templates ----------

def permission_summary(role):
    # Role list me "12 pages (3 edit)" jaisa chhota text
    items = _role_map(role, ignore_active=True)
    edits = sum(1 for level in items.values() if level >= R.LEVEL_EDIT)
    return len(items), edits
