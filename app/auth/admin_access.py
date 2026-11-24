# Phase 0 (P0-7): "Admin access" — sirf Developer. Tay karta hai ki Admin (aur uske banaye Staff roles) kaun se page par kya kar sakte hain.
# Table admin_ceiling (alag table, taaki normal Role screen se ye kabhi na badle). Users / Roles pages Admin ko hamesha milte hain (service.IMPLICIT_ADMIN_KEYS).
# Ceiling kam karne par roles ki rows nahi badalti — runtime par har Staff ke rights ceiling se clamp hote hain (service.permissions_of).
from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.auth import registry as R, service
from app.extensions import db
from app.models import AdminCeiling, Role

admin_access_bp = Blueprint("admin_access", __name__, url_prefix="/admin/access", template_folder="templates")


def _modules():
    # Matrix me sirf wahi jo ceiling me aa sakta hai: users / roles (implicit) aur developer-only keys nahi
    skip = set(service.IMPLICIT_ADMIN_KEYS) | R.DEVELOPER_ONLY_KEYS
    modules = []
    for block in R.tree():
        pages = [p for p in block["pages"] if p["key"] not in skip]
        if pages or block["specials"]:
            modules.append({"module": block["module"], "pages": pages, "specials": block["specials"]})
    return modules


def _ceiling_rows():
    return {row.page_key: row.level for row in AdminCeiling.query.all() if R.get(row.page_key)}


def _exceeding_roles(ceiling):
    # Roles jinki kuch rows ceiling se upar hain (runtime par clamp hoti hain) — Developer ko dikhane ke liye
    out = []
    for role in Role.query.filter_by(is_active=True).order_by(Role.name).all():
        over = []
        for perm in role.permissions:
            page = R.get(perm.page_key)
            if page is None or perm.page_key in R.DEVELOPER_ONLY_KEYS:
                continue
            allowed = R.LEVEL_EDIT if perm.page_key in service.IMPLICIT_ADMIN_KEYS else ceiling.get(perm.page_key, 0)
            if perm.level > allowed:
                over.append(page["label"])
        if over:
            out.append({"role": role.name, "pages": sorted(over)})
    return out


@admin_access_bp.route("/", methods=["GET", "POST"])
def access_page():
    modules = _modules()
    keys = [item["key"] for m in modules for item in m["pages"] + m["specials"]]
    rows = _ceiling_rows()
    if request.method == "POST":
        requested, errors = {}, []
        for key in keys:
            raw = request.form.get("perm__" + key)
            if raw is None:
                requested[key] = rows.get(key, 0)           # form me nahi aaya = jaisa tha waisa
            elif raw in ("0", "1", "2"):
                requested[key] = int(raw)
            else:
                errors.append("Invalid level for %s." % R.get(key)["label"])
        for name in request.form:                           # crafted unknown key
            if name.startswith("perm__") and name[6:] not in keys:
                errors.append("Unknown permission: %s" % name[6:46])
        for key, level in requested.items():
            page = R.get(key)
            if page["kind"] == "special" and level not in (0, R.LEVEL_EDIT):
                errors.append("Invalid level for %s." % page["label"])
            if page["kind"] == "special" and level and requested.get(page["page"], 0) < R.LEVEL_VIEW:
                errors.append("%s needs access to the %s page as well." % (page["label"], R.get(page["page"])["label"]))
        if errors:
            return render_template("admin/access.html", modules=modules, current=dict(rows, **{k: v for k, v in requested.items()}),
                                   allowed={k: R.LEVEL_EDIT for k in keys}, locked=set(), errors=errors, exceeding=_exceeding_roles(rows),
                                   active_nav="admin_access"), 400
        before = {k: v for k, v in rows.items() if k in keys}
        after = {k: v for k, v in requested.items() if v}
        added = {k: v for k, v in after.items() if k not in before}
        removed = {k: v for k, v in before.items() if k not in after}
        changed = {k: [before[k], after[k]] for k in after if k in before and before[k] != after[k]}
        if added or removed or changed:
            existing = {row.page_key: row for row in AdminCeiling.query.filter(AdminCeiling.page_key.in_(keys)).all()}
            for key, row in existing.items():
                if key not in after:
                    db.session.delete(row)
                elif row.level != after[key]:
                    row.level = after[key]
            for key, level in after.items():
                if key not in existing:
                    db.session.add(AdminCeiling(page_key=key, level=level))
            detail = {name: val for name, val in (("added", added), ("removed", removed), ("changed", changed)) if val}
            service.audit("admin_ceiling_changed", target_type="admin_ceiling", detail=detail)
            db.session.commit()
            flash("Admin access saved.", "success")
        else:
            flash("No changes to save.", "info")
        return redirect(url_for("admin_access.access_page"))
    return render_template("admin/access.html", modules=modules, current=rows, allowed={k: R.LEVEL_EDIT for k in keys}, locked=set(),
                           errors=[], exceeding=_exceeding_roles(rows), active_nav="admin_access")
