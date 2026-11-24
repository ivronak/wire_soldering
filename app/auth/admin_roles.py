# Phase 0 (P0-7): Roles screen — Administration. Role list, naya role, edit (naam + page matrix), copy, active / inactive.
# Matrix = har page par No access / View / View + Edit. Server hi final faisla karta hai (service.validate_role_permissions):
# koi bhi actor apne se zyada level nahi de sakta; jo keys actor ke liye "locked" hain (role me pehle se unse upar) ve badalti nahi.
import unicodedata

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy import func

from app.auth import registry as R, security, service
from app.extensions import db
from app.models import Role, RolePermission, User

admin_roles_bp = Blueprint("admin_roles", __name__, url_prefix="/admin/roles", template_folder="templates")

NAME_MAX = 60


def max_level(actor, key):
    # Actor is key par zyada se zyada kya level de sakta hai (0 = bilkul nahi)
    page = R.get(key)
    if page is None or key in R.DEVELOPER_ONLY_KEYS:
        return 0
    if actor.kind == service.KIND_DEVELOPER:
        return R.LEVEL_EDIT
    if key in service.MANAGER_KEYS and actor.kind != service.KIND_ADMIN:
        return 0
    level = min(service.level_of(actor, key), R.LEVEL_EDIT)
    return R.LEVEL_EDIT if page["kind"] == "special" and level else level


def role_current(role):
    # {key: level} us role ke asli rows (jo registry me valid hain)
    return {perm.page_key: perm.level for perm in role.permissions if R.get(perm.page_key) and perm.page_key not in R.DEVELOPER_ONLY_KEYS} if role else {}


def matrix_view(actor, role=None):
    # Template ko: modules (dev-only keys ke bina), allowed {key: max}, locked {keys jinme role ka level actor se upar hai}
    current = role_current(role)
    modules = []
    for block in R.tree():
        pages = [p for p in block["pages"] if p["key"] not in R.DEVELOPER_ONLY_KEYS]
        if pages or block["specials"]:
            modules.append({"module": block["module"], "pages": pages, "specials": block["specials"]})
    keys = [p["key"] for m in modules for p in m["pages"] + m["specials"]]
    allowed = {key: max_level(actor, key) for key in keys}
    locked = {key for key in keys if current.get(key, 0) > allowed[key]}
    return {"modules": modules, "allowed": allowed, "locked": locked, "current": current}


def _role_or_404(role_id):
    # Developer role non-Developer ko dikhta hi nahi (404)
    role = db.session.get(Role, role_id) if service.parse_id(role_id) else None
    if role is None or (role.system_key == service.KIND_DEVELOPER and service.current().kind != service.KIND_DEVELOPER):
        abort(404)
    return role


def _custom_role_or_404(role_id):
    # Developer / Admin built-in roles ka naam, rights aur status yahan se nahi badalte (Admin ke rights = "Admin access" screen)
    role = _role_or_404(role_id)
    if role.system_key:
        abort(403)
    return role


def _rank_guard(actor, role):
    # Apne se upar (ya bahar) ke rights wale role ko Manager chhed na sake: rename / pages / activate-deactivate / copy sab band (audit 23 Nov)
    if actor.kind != service.KIND_DEVELOPER and not service.role_within_actor(actor, role):
        abort(403)


def _own_role_guard(actor, role):
    # Staff manager apna hi role nahi badal sakta (khud ko lock-out / confusion se bachne ke liye)
    if actor.kind == service.KIND_STAFF and actor.role_id == role.id:
        abort(403)


def _parse_levels(form):
    # perm__<key> = 0 / 1 / 2. Wapas: ({key: level}, errors). Unknown key / ganda level = error (crafted POST).
    requested, errors = {}, []
    for name, raw in form.items():
        if not name.startswith("perm__"):
            continue
        key = name[len("perm__"):]
        if R.get(key) is None:
            errors.append("Unknown permission: %s" % key[:40])
            continue
        if raw not in ("0", "1", "2"):
            errors.append("Invalid level for %s." % R.get(key)["label"])
            continue
        requested[key] = int(raw)
    return requested, errors


def _skeleton(name):
    # Naam ka "chehra": NFKC + zero-width / control akshar hatao + casefold — taaki "Admin" ki nakal ("Admin" + zero-width) pakdi jaye
    text = unicodedata.normalize("NFKC", name)
    text = "".join(ch for ch in text if unicodedata.category(ch) not in ("Cf", "Cc"))
    return " ".join(text.casefold().split())


def _mixed_script(name):
    # Latin ke saath doosri script ke akshar (jaise Cyrillic A) milaye ho to nakal-naam ka khatra: refuse
    letters = [ch for ch in name if ch.isalpha()]
    has_latin = any(unicodedata.name(ch, "").startswith("LATIN") for ch in letters)
    has_other = any(not unicodedata.name(ch, "LATIN").startswith("LATIN") for ch in letters)
    return has_latin and has_other


def _name_problem(name, role_id=None):
    if not name:
        return "Role name is required."
    if len(name) > NAME_MAX:
        return "Role name is too long (max %d characters)." % NAME_MAX
    problem = security.visible_name_problem(name, "Role name")
    if problem:
        return problem
    if _mixed_script(name):
        return "Role name cannot mix letters from different alphabets."
    key = security.look_alike_key(name)
    if _skeleton(name) in ("admin", "developer") or key in ("admin", "developer"):
        return "A role with this name already exists."
    query = Role.query.filter(func.lower(Role.name) == name.lower())
    if role_id:
        query = query.filter(Role.id != role_id)
    if query.first() is not None:
        return "A role with this name already exists."
    if key.isascii():
        # Latin naam ka chehra kisi maujooda role jaisa ho (combining mark / invisible se bana nakal) to refuse; Devanagari jaise naam isse bachte hain
        for other in Role.query.all():
            if other.id != role_id and security.look_alike_key(other.name) == key:
                return "A role with this name already exists."
    return None


def _compute_final(actor, role, requested):
    # Role ki nayi {key: level}: jo keys locked / actor ke bas ke bahar hain wo jaisi thi waisi; baaki form se. Level 0 = row hata do.
    current = role_current(role)
    final = {key: level for key, level in current.items() if level > max_level(actor, key)}      # locked — chhedna nahi
    for key, level in requested.items():
        if key not in final and level:                     # actor ke bas se bahar ka level ho to validate error dega
            final[key] = level
    for key, level in current.items():
        if key not in final and key not in requested:      # form me aayi hi nahi = jaisi thi waisi
            final[key] = level
    return final


def _diff(before, after):
    added = {k: v for k, v in after.items() if k not in before}
    removed = {k: v for k, v in before.items() if k not in after}
    changed = {k: [before[k], after[k]] for k in after if k in before and before[k] != after[k]}
    return {key: val for key, val in (("added", added), ("removed", removed), ("changed", changed)) if val}


def _apply_permissions(role, final):
    existing = {perm.page_key: perm for perm in role.permissions}
    for key, perm in list(existing.items()):
        if key not in final:
            role.permissions.remove(perm)
    for key, level in final.items():
        if key in existing:
            existing[key].level = level
        else:
            role.permissions.append(RolePermission(page_key=key, level=level))


def _render_form(actor, role, values, errors, status=200):
    view = matrix_view(actor, role)
    if values.get("levels") is not None:
        # galti ke baad user ka bhara hua form wapas dikhao, par locked keys role ke asli level par hi
        view["current"] = dict(values["levels"], **{k: view["current"][k] for k in view["locked"]})
    return render_template("admin/role_form.html", role=role, values=values, errors=errors, active_nav="roles", level_names=R.LEVEL_NAMES, **view), status


@admin_roles_bp.route("/")
def roles_list():
    actor = service.current()
    counts = dict(db.session.query(User.role_id, func.count(User.id)).filter(User.is_active == True, User.role_id != None).group_by(User.role_id).all())  # noqa: E711,E712
    rows = []
    for role in Role.query.order_by(Role.system_key.is_(None), Role.is_active.desc(), Role.name).all():
        if role.system_key == service.KIND_DEVELOPER and actor.kind != service.KIND_DEVELOPER:
            continue                                        # Developer role sirf Developer ko dikhta hai
        pages, edits = service.permission_summary(role)
        if role.system_key == service.KIND_DEVELOPER:
            pages, edits = len(R.all_keys()), len(R.all_keys())
        elif role.system_key == service.KIND_ADMIN:
            ceiling = service.ceiling_map()
            pages, edits = len(ceiling), sum(1 for v in ceiling.values() if v >= R.LEVEL_EDIT)
        own = actor.kind == service.KIND_STAFF and actor.role_id == role.id
        # Custom role ke liye: "Admin access" ceiling ke baad asli kitna milta hai (blocked pages ka note list me dikhane ke liye)
        blocked, real_pages, real_edits = [], pages, edits
        if not role.system_key:
            real_pages, real_edits, blocked = service.ceiling_gap(role)
        rows.append({"role": role, "pages": pages, "edits": edits, "users": counts.get(role.id, 0), "own": own,
                     "within": service.role_within_actor(actor, role), "blocked": blocked, "real_pages": real_pages, "real_edits": real_edits})
    # Kisi bhi active custom role ke pages ceiling se kat rahe ho to list ke upar ek saaf warning
    blocked_roles = sum(1 for r in rows if r["blocked"] and r["role"].is_active)
    return render_template("admin/roles.html", rows=rows, active_nav="roles", can_add=service.user_can(actor, "roles", R.LEVEL_EDIT),
                           blocked_roles=blocked_roles, is_developer=actor.kind == service.KIND_DEVELOPER)


@admin_roles_bp.route("/new", methods=["GET", "POST"])
def roles_new():
    actor = service.current()
    if request.method == "GET":
        return _render_form(actor, None, {"name": "", "description": ""}, [])
    name = (request.form.get("name") or "").strip()
    description = (request.form.get("description") or "").strip()[:200]
    requested, errors = _parse_levels(request.form)
    values = {"name": name, "description": description, "levels": {k: v for k, v in requested.items() if v}}
    problem = _name_problem(name)
    if problem:
        errors.append(problem)
    final = _compute_final(actor, None, requested)
    errors += service.validate_role_permissions(actor, final)
    if errors:
        return _render_form(actor, None, values, errors, 400)
    role = Role(name=name, description=description or None)
    db.session.add(role)
    db.session.flush()
    _apply_permissions(role, final)
    service.audit("role_created", target_type="role", target_id=role.id, detail={"name": name, "permissions": final})
    db.session.commit()
    flash("Role created.", "success")
    return redirect(url_for("admin_roles.roles_list"))


@admin_roles_bp.route("/<int:role_id>/edit", methods=["GET", "POST"])
def roles_edit(role_id):
    actor = service.current()
    role = _custom_role_or_404(role_id)
    _own_role_guard(actor, role)
    _rank_guard(actor, role)
    if request.method == "GET":
        return _render_form(actor, role, {"name": role.name, "description": role.description or ""}, [])
    name = (request.form.get("name") or "").strip()
    description = (request.form.get("description") or "").strip()[:200]
    requested, errors = _parse_levels(request.form)
    values = {"name": name, "description": description, "levels": {k: v for k, v in requested.items() if v}}
    problem = _name_problem(name, role.id)
    if problem:
        errors.append(problem)
    final = _compute_final(actor, role, requested)
    before = role_current(role)
    # Sirf badli hui keys ko validate karo: purani (actor ke bas ke bahar wali) rows par actor ko galat na thehrao
    changed = {k: v for k, v in final.items() if before.get(k) != v}
    errors += service.validate_role_permissions(actor, changed, whole=final)
    for key in final:                                       # purani special bhi tab tak hi theek jab uska page bacha ho
        page = R.get(key)
        if page and page["kind"] == "special" and key not in changed and final.get(page["page"], 0) < R.LEVEL_VIEW:
            errors.append("%s needs access to the %s page as well." % (page["label"], R.get(page["page"])["label"]))
    if errors:
        return _render_form(actor, role, values, errors, 400)
    changes = _diff(before, final)
    detail = {}
    if role.name != name:
        detail["renamed"] = [role.name, name]
        role.name = name
    if (role.description or "") != description:
        detail["description_changed"] = True
        role.description = description or None
    if changes:
        detail["permissions"] = changes
        _apply_permissions(role, final)
    if detail:
        service.audit("role_permissions_changed" if changes else "role_updated", target_type="role", target_id=role.id,
                      detail=dict(detail, role=role.name))
        db.session.commit()
        flash("Role saved.", "success")
    else:
        flash("No changes to save.", "info")
    return redirect(url_for("admin_roles.roles_list"))


@admin_roles_bp.route("/<int:role_id>/copy")
def roles_copy(role_id):
    # Copy ab DB me KUCH nahi banata (pehle yahin role ban jaata tha — form band karne par bhi bina confirm ke role reh jaata tha).
    # Sirf "Add role" form kholta hai: naam "Copy of X" + source ke pages pehle se bhare. Role tabhi banta hai jab user "Save role" dabaye
    # (wo POST roles_new par jaata hai, jahan naam / rights ki saari checking hoti hai). Copy me sirf wahi rows aati hain jo actor khud de sakta hai.
    actor = service.current()
    source = _custom_role_or_404(role_id)
    _rank_guard(actor, source)
    base = ("Copy of " + source.name)[:NAME_MAX - 4]
    name, n = base, 1
    while Role.query.filter(func.lower(Role.name) == name.lower()).first() is not None:
        n += 1
        name = "%s (%d)" % (base, n)
    levels = {key: min(level, max_level(actor, key)) for key, level in role_current(source).items() if max_level(actor, key) > 0}
    values = {"name": name, "description": source.description or "", "levels": levels, "copied_from": source.name}
    return _render_form(actor, None, values, [])


@admin_roles_bp.route("/<int:role_id>/toggle", methods=["POST"])
def roles_toggle(role_id):
    actor = service.current()
    role = _custom_role_or_404(role_id)
    _own_role_guard(actor, role)
    _rank_guard(actor, role)
    if role.is_active:
        in_use = User.query.filter_by(role_id=role.id, is_active=True).count()
        if in_use:
            flash("%d active user(s) still have this role. Move them to another role first." % in_use, "error")
            return redirect(url_for("admin_roles.roles_list"))
    role.is_active = not role.is_active
    service.audit("role_activated" if role.is_active else "role_deactivated", target_type="role", target_id=role.id, detail={"role": role.name})
    db.session.commit()
    flash("Role activated." if role.is_active else "Role deactivated.", "success")
    return redirect(url_for("admin_roles.roles_list"))
