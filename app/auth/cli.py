# Phase 0 (P0-2): server ke terminal se chalne wale 3 command — Developer banana, password reset, unlock.
# Ye kabhi web se nahi chalte (isliye koi web user khud ko Developer nahi bana sakta). Password argv me nahi, hidden prompt se.
#   flask create-developer --mobile 9XXXXXXXXX --name "Owner"
#   flask reset-password --mobile 9XXXXXXXXX
#   flask unlock-user --mobile 9XXXXXXXXX
# Live par ye command service user (porta1691) se chalao, root se nahi — warna DB file root-owned ho jaati hai ("readonly database").
import click

from app.auth import lockout, security, service
from app.extensions import db
from app.models import Role, User


def _clean_mobile(value):
    mobile = security.normalize_mobile(value)
    if not mobile:
        raise click.ClickException("Mobile number must be a valid 10-digit Indian mobile number (starting with 6-9).")
    return mobile


def _ask_password(mobile):
    password = click.prompt("New password", hide_input=True, confirmation_prompt=True)
    problem = security.password_problem(password, mobile)
    if problem:
        raise click.ClickException(problem)
    return password


def _require_secret_key(app):
    # Lockout rows secret-key se bane hash par hain: key ke bina CLI "unlock" bol dega par kuch nahi hata paayega (audit 23 Nov)
    if app.config.get("AUTH_CONFIG_PROBLEM"):
        raise click.ClickException("%s Set ERP_SECRET_KEY (same value as the web service) before running this command." % app.config["AUTH_CONFIG_PROBLEM"])


def register_cli(app):
    @app.cli.command("create-developer")
    @click.option("--mobile", required=True, help="10-digit mobile number (login ID)")
    @click.option("--name", default="Developer", show_default=True, help="Display name")
    def create_developer(mobile, name):
        """Create a Developer account (the owner; sees everything, hidden from Admins)."""
        _require_secret_key(app)
        mobile = _clean_mobile(mobile)
        if User.query.filter_by(mobile=mobile).first():
            raise click.ClickException("A user with this mobile number already exists.")
        password = _ask_password(mobile)
        role = Role.query.filter_by(system_key=service.KIND_DEVELOPER).first()
        if role is None:
            raise click.ClickException("The Developer role is missing. Run 'flask db upgrade' first.")
        user = User(full_name=name.strip() or "Developer", mobile=mobile, password_hash=security.hash_password(password),
                    role_id=role.id, must_change_password=False)
        db.session.add(user)
        db.session.flush()
        service.audit("developer_created", target_type="user", target_id=user.id, label="server CLI")
        db.session.commit()
        click.echo("Developer created (login with the mobile number ending %s)." % mobile[-4:])

    @app.cli.command("reset-password")
    @click.option("--mobile", required=True, help="Mobile number of the user")
    def reset_password(mobile):
        """Set a new password for any user (break-glass when nobody can log in)."""
        _require_secret_key(app)
        mobile = _clean_mobile(mobile)
        user = User.query.filter_by(mobile=mobile).first()
        if user is None:
            raise click.ClickException("No user with this mobile number.")
        password = _ask_password(mobile)
        user.password_hash = security.hash_password(password)
        user.must_change_password = user.kind != service.KIND_DEVELOPER     # Developer apna password khud tay karta hai
        user.session_version += 1                                           # purane sab session band
        lockout.clear_all_for_mobile(mobile)
        service.audit("password_reset_cli", target_type="user", target_id=user.id, label="server CLI")
        db.session.commit()
        click.echo("Password updated for the user ending %s." % mobile[-4:])

    @app.cli.command("unlock-user")
    @click.option("--mobile", required=True, help="Mobile number of the user")
    def unlock_user(mobile):
        """Clear the login lock / failed-attempt counter for a mobile number."""
        _require_secret_key(app)
        mobile = _clean_mobile(mobile)
        removed = lockout.clear_all_for_mobile(mobile)
        user = User.query.filter_by(mobile=mobile).first()
        service.audit("unlock_cli", target_type="user", target_id=user.id if user else None, label="server CLI")
        db.session.commit()
        click.echo("Cleared %d lock record(s) for the number ending %s." % (removed, mobile[-4:]))
