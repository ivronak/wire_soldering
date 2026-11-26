# Phase 0 (P0-7): Users screen — Administration. List, naya user, edit (naam / role), password reset, unlock, active / inactive.
# Add / Edit alag page nahi: list ke upar side drawer me khulta hai (templates/admin/users.html). GET /new aur GET /<id>/edit bhi
# wahi list dikhate hain, drawer pehle se khula (seedhe link ke liye); galat input par POST wahi drawer error ke saath wapas deta hai.
# Rank rules (flow doc 10.1 + 11.1) sab service.py ke can_manage_user / can_assign_role se: koi bhi kaam server par dobara check hota hai,
# UI me button chhupana sirf suvidha hai. Developer role wale users sirf Developer ko dikhte hain (visible_users_query).
# User ka koi alag "type" nahi — har user ka sirf ek Role (Developer / Admin bhi roles hain).
# Temp password sirf POST ke jawab me ek baar dikhta hai (redirect / flash me nahi — cookie me chala jaata), page no-store hai.
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy import func, or_

from app.auth import lockout, security, service
from app.extensions import db
from app.models import LoginAttempt, Role, User
from app.timeutil import utc_now

admin_users_bp = Blueprint("admin_users", __name__, url_prefix="/admin/users", template_folder="templates")

ROLE_ORDER = {service.KIND_DEVELOPER: 0, service.KIND_ADMIN: 1}      # Developer, Admin upar; baaki custom roles naam se

def generate_next_user_code():
    
    last_user = User.query.order_by(User.id.desc()).first()
    if not last_user:
        return "USR-001"

    next_user = last_user.id + 1
    return f"USR-{next_user:03d}"    

def _locked_mobile_hashes():
    now = utc_now()
    return {row.mobile_hash for row in LoginAttempt.query.filter(LoginAttempt.locked_until != None, LoginAttempt.locked_until > now).all()}  # noqa: E711


def _target_or_404(user_id):
    target = service.get_visible_user(service.current(), user_id)
    if target is None:
        abort(404)
    return target


def _manageable_or_403(target):
    if not service.can_manage_user(service.current(), target):
        abort(403)


def _credentials_page(user, temp_password, heading):
    # Temp password ek hi baar, seedha response me. Page no-store (guard ka after_request lagata hai).
    return render_template("admin/credentials.html", target=user, temp_password=temp_password, heading=heading, active_nav="users")


def _render_list(drawer=None, status_code=200):
    # Users list + (optional) side drawer. Add / Edit ab alag page nahi — baaki masters ki tarah side me form kholta hai.
    # drawer = None (band) ya {"mode": "add" / "edit", "target": User ya None, "values": {...}, "error": text ya None}:
    #   POST me galti ho to wahi drawer bhara hua + error ke saath dobara khulta hai (user ka likha hua gayab nahi hota).
    actor = service.current()
    q = (request.args.get("q") or "").strip()
    status = (request.args.get("status") or "all").lower()
    base = service.visible_users_query(actor)
    # Role filter: sirf wahi roles jinke koi user actor ko dikhte hain (Developer role Admin ko nahi dikhta); ajeeb / purani id = filter nahi
    role_counts = dict(base.with_entities(User.role_id, func.count(User.id)).group_by(User.role_id).all())
    role_options = sorted((r for r in Role.query.filter(Role.id.in_(list(role_counts))).all()),
                          key=lambda r: (ROLE_ORDER.get(r.system_key, 2), r.name.lower()))
    role_filter = service.parse_id(request.args.get("role"))
    if role_filter not in role_counts:
        role_filter = None
    if role_filter:
        base = base.filter(User.role_id == role_filter)
    total, active_count = base.count(), base.filter(User.is_active == True).count()  # noqa: E712 (All / Active / Inactive ginti role filter ke andar)
    query = base
    if q:
        like = "%" + q + "%"
        query = query.filter(or_(User.full_name.ilike(like), User.mobile.ilike(like)))
    if status == "active":
        query = query.filter(User.is_active == True)  # noqa: E712
    elif status == "inactive":
        query = query.filter(User.is_active == False)  # noqa: E712
    users = sorted(query.all(), key=lambda u: (ROLE_ORDER.get(u.role.system_key, 2), (u.full_name or "").lower()))
    locked = _locked_mobile_hashes()
    rows = [{"user": u, "manage": service.can_manage_user(actor, u), "locked": security.mobile_hash(u.mobile) in locked} for u in users]
    roles = service.assignable_roles(actor)
    if drawer and drawer.get("target") is not None and drawer["target"].role not in roles:
        roles.append(drawer["target"].role)     # user ka mojooda role hamesha dropdown me (unchanged save ho sake — peer manager / inactive role par bhi)
    next_user=generate_next_user_code()    
    return render_template("admin/users.html", rows=rows, q=q, status=status, total=total, active_count=active_count,
                           inactive_count=total - active_count, active_nav="users", can_add=service.user_can(actor, "users", 2),
                           roles=roles, drawer=drawer, role_options=role_options, role_counts=role_counts, role_filter=role_filter, next_code=next_user), status_code


@admin_users_bp.route("/")
def users_list():
    return _render_list()


def _form_values():
    return {"full_name": (request.form.get("full_name") or "").strip(), "mobile": (request.form.get("mobile") or "").strip(),
            "role_id": request.form.get("role_id") or ""}


@admin_users_bp.route("/new", methods=["GET", "POST"])
def users_new():
    actor = service.current()
    if request.method == "GET":
        return _render_list(drawer={"mode": "add", "target": None, "values": {}, "error": None})      # list + khula Add drawer
    values = _form_values()
    error = None
    mobile = security.normalize_mobile(values["mobile"])
    role_id = service.parse_id(values["role_id"])
    role = db.session.get(Role, role_id) if role_id else None
    if not values["full_name"]:
        error = "Name is required."
    elif len(values["full_name"]) > 100:
        error = "Name is too long."
    elif security.visible_name_problem(values["full_name"], "Name"):
        error = security.visible_name_problem(values["full_name"], "Name")
    elif mobile is None:
        error = "Enter a valid 10-digit mobile number."
    elif User.query.filter_by(mobile=mobile).first() is not None:
        # Jo user actor ko dikhta hi nahi (Developer) uske number par "registered" nahi bolte — warna Developer ka number pata chal jata
        visible = service.visible_users_query(actor).filter(User.mobile == mobile).first() is not None
        error = "This mobile number is already registered." if visible else "This mobile number cannot be used."
    elif role is None or not service.can_assign_role(actor, role):
        error = "Choose a role from the list."                    # Developer role kisi ko nahi milta; Admin role sirf Developer de sakta hai
    if error:
        return _render_list(drawer={"mode": "add", "target": None, "values": values, "error": error}, status_code=400)
    temp_password = security.generate_temp_password()
    user = User(code=generate_next_user_code(), full_name=values["full_name"], mobile=mobile, password_hash=security.hash_password(temp_password),
                role_id=role.id, must_change_password=True, created_by_id=actor.id)
    db.session.add(user)
    db.session.flush()
    service.audit("user_created", target_type="user", target_id=user.id,
                  detail={"role": role.name, "mobile": security.mask_mobile(mobile)})
    db.session.commit()
    return _credentials_page(user, temp_password, "User created")


@admin_users_bp.route("/<int:user_id>/edit", methods=["GET", "POST"])
def users_edit(user_id):
    actor = service.current()
    target = _target_or_404(user_id)
    _manageable_or_403(target)
    if request.method == "GET":
        return _render_list(drawer={"mode": "edit", "target": target, "error": None, "values": {
            "full_name": target.full_name, "mobile": target.mobile, "role_id": str(target.role_id)}})
    values = _form_values()
    error = None
    role = None
    if not values["full_name"] or len(values["full_name"]) > 100:
        error = "Enter the user's name (up to 100 characters)."
    elif security.visible_name_problem(values["full_name"], "Name"):
        error = security.visible_name_problem(values["full_name"], "Name")
    else:
        role_id = service.parse_id(values["role_id"])
        role = db.session.get(Role, role_id) if role_id else None
        unchanged = role is not None and role.id == target.role_id
        if role is None or (not unchanged and not service.can_assign_role(actor, role)):
            error = "Choose a role from the list."
    if error:
        values["mobile"] = target.mobile
        return _render_list(drawer={"mode": "edit", "target": target, "values": values, "error": error}, status_code=400)
    changes = {}
    if target.full_name != values["full_name"]:
        changes["name"] = [target.full_name, values["full_name"]]
        target.full_name = values["full_name"]
    if role.id != target.role_id:
        changes["role"] = [target.role.name, role.name]
        target.role_id = role.id
        # Yahan session_version +1 NAHI karte: rights har request par DB se aate hain (service.permissions_of), isliye user logout kiye
        # bina agle page-load / refresh par naye role ke rights mil jaate hain. (Pehle yahan +1 tha — usse user bahar nikal jaata tha.)
    if changes:
        service.audit("user_updated", target_type="user", target_id=target.id, detail=changes)
        db.session.commit()
        flash("User updated.", "success")
    return redirect(url_for("admin_users.users_list"))


@admin_users_bp.route("/<int:user_id>/reset", methods=["POST"])
def users_reset(user_id):
    target = _target_or_404(user_id)
    _manageable_or_403(target)
    temp_password = security.generate_temp_password()
    target.password_hash = security.hash_password(temp_password)
    target.must_change_password = True
    target.session_version += 1
    lockout.clear_all_for_mobile(target.mobile)
    service.audit("password_reset", target_type="user", target_id=target.id)
    db.session.commit()
    return _credentials_page(target, temp_password, "Password reset")


@admin_users_bp.route("/<int:user_id>/unlock", methods=["POST"])
def users_unlock(user_id):
    target = _target_or_404(user_id)
    _manageable_or_403(target)
    lockout.clear_all_for_mobile(target.mobile)
    service.audit("user_unlocked", target_type="user", target_id=target.id)
    db.session.commit()
    flash("User unlocked.", "success")
    return redirect(url_for("admin_users.users_list"))


@admin_users_bp.route("/<int:user_id>/toggle", methods=["POST"])
def users_toggle(user_id):
    # Hard delete nahi — sirf Active / Inactive (audit trail ke liye). Apne aap ko aur aakhri Admin ko band nahi kar sakte.
    actor = service.current()
    target = _target_or_404(user_id)
    _manageable_or_403(target)
    if target.is_active and target.role.system_key == service.KIND_ADMIN and actor.kind != service.KIND_DEVELOPER:
        if User.query.join(Role, User.role_id == Role.id).filter(Role.system_key == service.KIND_ADMIN, User.is_active == True).count() <= 1:  # noqa: E712
            flash("The last active Admin cannot be deactivated.", "error")
            return redirect(url_for("admin_users.users_list"))
    if not target.is_active and not target.role.is_active:
        flash("This user's role is inactive. Activate the role or move the user to another role first.", "error")
        return redirect(url_for("admin_users.users_list"))
    target.is_active = not target.is_active
    target.session_version += 1                # band karte hi uska khula session agli request par khatam
    service.audit("user_activated" if target.is_active else "user_deactivated", target_type="user", target_id=target.id)
    db.session.commit()
    flash("User activated." if target.is_active else "User deactivated.", "success")
    return redirect(url_for("admin_users.users_list"))
