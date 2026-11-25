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


# ---------- "kaun ne kiya" helpers (U1; flow doc: user_in_erp_flow_2026_11_24.md) ----------
# Do tarah ka "kaun":  W1 actor = jisne ERP me button dabaya (session se apne aap, created_by_id jaise columns)
#                      W2 zimmedar = jisne kaam kiya (operator / inspector / issued_by ... — dropdown se chuna)
# Developer ka niyam (user, 24 Nov): Developer kisi dropdown me NAHI aata; Developer ne action kiya to DB me uski asli id,
# par dusron ko (aur print par) "Administrator" dikhta hai.

DEVELOPER_PUBLIC_LABEL = "Administrator"


def actor_id():
    # W1: abhi logged-in user ki id (naye document / cancel / approve par `*_by_id` me jaati hai). Login nahi (CLI / script) = None.
    user = current()
    return user.id if user is not None else None


def pickable_users_query():
    # W2 dropdown ki list: active user + active role + role Developer NAHI — dekhne wala chahe Developer khud ho (visible_users_query se alag:
    # wo "kaun kise manage kare" ka rule hai, ye "kaun kaam ke liye chuna ja sakta hai" ka).
    return (User.query.join(Role, User.role_id == Role.id)
            .filter(User.is_active == True, Role.is_active == True,  # noqa: E712
                    or_(Role.system_key.is_(None), Role.system_key != KIND_DEVELOPER)))


def pickable_users():
    # Dropdown ke liye list, naam se sorted (har naam ke saath role pick_label me dikhta hai)
    return sorted(pickable_users_query().all(), key=lambda u: ((u.full_name or "").lower(), u.id))


def resolve_pickable(raw):
    # W2 field ki chuni hui id ko server par dobara check karo (crafted POST se Developer / inactive / ajeeb id andar na aaye).
    # Wapas: User ya None (None = galat id, caller error de).
    user_id = parse_id(raw)
    if user_id is None:
        return None
    return pickable_users_query().filter(User.id == user_id).first()


def pickable_options():
    # Dropdown ke liye JSON-friendly list [{"id", "label"}] — JS se bane form (jaise Complete stage ka "Taken by") yahi use karte hain
    return [{"id": u.id, "label": pick_label(u)} for u in pickable_users()]


def my_pick_id():
    # Login user ki id agar wo dropdown me aa sakta hai (Developer nahi aata -> None), warna None. "default = main hi" ke liye.
    user = current()
    if user is None:
        return None
    return user.id if pickable_users_query().filter(User.id == user.id).first() is not None else None


def read_picked_user(form, field, required=False, label="the person"):
    # W2 field ka common reader: form me `<field>_user_id` aata hai (dropdown se). Wapas (user, error):
    #   khaali + required nahi   -> (None, None)   field optional tha, kuch nahi chuna
    #   khaali + required        -> (None, "Choose <label>.")
    #   galat / Developer / inactive id (crafted POST) -> (None, "Choose <label> from the list.")
    #   theek                    -> (User, None)  caller `<field>_user_id = user.id` aur text snapshot `<field> = user.full_name` rakhta hai
    raw = (form.get("%s_user_id" % field) or "").strip()
    if not raw:
        return None, ("Choose %s." % label if required else None)
    user = resolve_pickable(raw)
    if user is None:
        return None, "Choose %s from the list." % label
    return user, None


def pick_label(user):
    # Dropdown me "Ramesh — Operator": role se pata chale banda kaun hai (user ka faisla: role = pehchaan)
    return "%s — %s" % (user.full_name, user.role.name if user.role else "")


def actor_label(user, viewer=None):
    # W1 / W2 ka naam dikhane ke liye. user None = None (template "—" lagayega).
    # Developer ka naam sirf Developer viewer ko; baaki sab (viewer None = print / bahar jaane wala document) ko "Administrator".
    if user is None:
        return None
    is_developer = user.role is not None and user.role.system_key == KIND_DEVELOPER
    if is_developer and not (viewer is not None and viewer.kind == KIND_DEVELOPER):
        return DEVELOPER_PUBLIC_LABEL
    return user.full_name


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

def ceiling_gap(role):
    # Role me jo pages diye hain par Admin ceiling ("Admin access" screen) unhe poora nahi deti — runtime par staff ko min(role, ceiling) hi milta hai.
    # Wapas: (effective_pages, effective_edits, blocked) — blocked = [(page label, role level, asli level)]; Roles list ka note isi se banta hai.
    ceiling = ceiling_map()
    pages = edits = 0
    blocked = []
    for key, level in _role_map(role, ignore_active=True).items():
        real = min(level, ceiling.get(key, 0))
        if real:
            pages += 1
            edits += 1 if real >= R.LEVEL_EDIT else 0
        if real < level:
            blocked.append((R.get(key)["label"], level, real))
    return pages, edits, blocked


def permission_summary(role):
    # Role list me "12 pages (3 edit)" jaisa chhota text
    items = _role_map(role, ignore_active=True)
    edits = sum(1 for level in items.values() if level >= R.LEVEL_EDIT)
    return len(items), edits
