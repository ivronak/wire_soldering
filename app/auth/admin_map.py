# Phase 0: Administration screens (Users, Roles, Admin access, Audit log) ke permission rule.
# Users / Roles: "users" / "roles" page key se (Admin ko hamesha, Staff ko sirf jab uske role me ho).
# Admin access / Audit log: sirf Developer role wale user ko; koi custom role ya ceiling row inhe kabhi nahi khol sakti.
from app.auth import registry as R
from app.auth.guard_map import Rule

V, E = R.LEVEL_VIEW, R.LEVEL_EDIT

PAGE_BLUEPRINTS = {"admin_users": "users", "admin_roles": "roles"}
DEVELOPER_BLUEPRINTS = {"admin_access", "admin_audit"}
# Form kholna (GET) bhi badalne ka kaam hai (jaise quotations_new) -> Edit; sirf View wale ko khaali form nahi dikhta
FORM_ENDPOINTS = {"admin_users.users_new", "admin_users.users_edit", "admin_roles.roles_new", "admin_roles.roles_edit", "admin_roles.roles_copy"}


def resolve(endpoint, mutating):
    blueprint = endpoint.split(".")[0] if "." in endpoint else endpoint
    if blueprint in PAGE_BLUEPRINTS:
        return Rule("page", (PAGE_BLUEPRINTS[blueprint],), E if (mutating or endpoint in FORM_ENDPOINTS) else V, False)
    if blueprint in DEVELOPER_BLUEPRINTS:
        return Rule("developer", (), 0, False)
    return None
