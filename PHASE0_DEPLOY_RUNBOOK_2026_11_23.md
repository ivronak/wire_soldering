# Phase 0 (login + roles) — live deploy runbook

**Status: PREPARED ONLY. Nothing committed, pushed or deployed. Deploy sirf tab jab user bole "deploy / live karo".**
Tooling: `scripts/deploy_phase0/update_live_bundle_phase0.sh` (login-aware version of the old `update_live_bundle.sh`) + `scripts/deploy_phase0/staging_sweep.py` (page sweep with a staging Developer login). Syntax-checked and the sweep tested locally; the shell script has NOT been run on the server.

## Why this deploy is different from the earlier ones
1. After deploy **every page needs login**. The old health check (plain `curl` of 30 pages expecting 200) would see 302 everywhere and auto-rollback. The new script checks: `/login` = 200, anonymous pages = 302 (guard alive), then (optional) a **real login POST on the public hostname** and a logged-in sweep.
2. The app **refuses every web request** (503) if `ERP_SECRET_KEY` is missing / shorter than 32 chars on the live server (fail-closed). The script checks `/etc/wire-soldering.env` first and stops with live untouched.
3. Three new libraries: `Flask-Login==0.6.3`, `Flask-WTF==1.2.2`, `WTForms==3.2.1` (pinned for the server's **Python 3.9**). The script pip-installs them into the live venv before the switch (additive; old code does not import them, so rollback is safe).
4. Until the first **Developer** account exists nobody can log in. The app stays locked (data is safe). Create it right after deploy (below).
5. Three new migrations (additive; no existing ERP table changes): `d4e1b7a9c2f5` (users, roles, role_permissions, admin_ceiling, audit_log), `e5f2c8b0d3a6` (login_attempts) and `f7b1d4e8a2c6` (**roles-only**: no user "type" any more - Developer and Admin are built-in roles, `roles.system_key`; the 6 starter roles are removed again). After deploy the only roles are **Developer** and **Admin**; every other role is created by the Admin on the Roles screen.

## Before deploy (my side — done / to redo right before)
- [ ] Final full test: `t_auth` (login/guard/CSRF), `t_admin` (admin screens), `t_ui` view/edit/parity for all 47 keys, old regression harnesses, Developer-parity crawl (205 baseline pages identical).
- [ ] Final security review workflow findings fixed.
- [ ] Commit (only when the user says), `git bundle create <scratchpad>/deploy/wire.bundle HEAD main`.
- [ ] Beta first if the user wants (the beta host sits behind the same LiteSpeed proxy: confirm CSRF + secure cookie + real client IP work there).

## Before deploy (user / server side)
- [ ] `/etc/wire-soldering.env` has `ERP_SECRET_KEY=` a random string of 32+ characters (it already exists for the service; check length: `grep -c '^ERP_SECRET_KEY=.\{32,\}' /etc/wire-soldering.env` → 1). **Changing the key later logs everyone out** (sessions) — fine, but note: the lockout table hashes mobile numbers with this key, so old lock entries stop matching (harmless).
- [ ] Decide the Developer mobile number (10 digits, login ID) and a strong password (min 10 chars, not only digits, not containing the mobile).
- [ ] Optional: `/root/deploy_wire/health.cred` (chmod 600): line 1 = Developer mobile, line 2 = password → lets the script prove a real login. **Delete it after the deploy.**

## Deploy
1. Upload bundle + script (same as before: `run_update_bundle.sh` pattern, but with `update_live_bundle_phase0.sh`).
2. Script: backup → staging on a copy of the live DB (migrate + login sweep + selfcheck) → stop → ff-merge → migrate → start → health. Any failure → automatic rollback (code + DB restored), live stays on the old version.
3. **Right after** (interactive, service user — NOT root, otherwise the DB file becomes root-owned and SQLite says "readonly database"):
   ```
   ssh -t root@<server> "runuser -u porta1691 -- env HOME=/home/portal.ivinfotech.com FLASK_APP=run.py ERP_SECRET_KEY=\$(grep ^ERP_SECRET_KEY= /etc/wire-soldering.env | cut -d= -f2-) /home/portal.ivinfotech.com/wire_soldering/venv/bin/flask create-developer --mobile 9XXXXXXXXX --name 'Owner'"
   ```
   (it asks the password twice, hidden).
4. Log in at https://portal.ivinfotech.com/login → **Admin access** (Developer only): tick which pages Admins may use → **Users**: create the Admin(s) (role = Admin) → Admin creates his own roles on **Roles** (there are no starter roles) → then creates users and gives each one a role.
5. Delete `/root/deploy_wire/health.cred`.

## Break-glass (no web UI needed)
- Forgot Developer password / locked out: `flask reset-password --mobile <10 digit>` (same `runuser` form as above), `flask unlock-user --mobile <10 digit>`.
- Whole deploy bad: backup folder `/root/deploy_wire/backups/phase0_<timestamp>/` (`code_before.tgz`, `erp_before.db`, `old_head.txt`); the script already rolls back automatically on a failed step.
- Emergency app lock-out because of a code bug: `git reset --hard <old_head>` + restore `erp_before.db` (new tables vanish with the DB copy; users created after the deploy are lost — export is not needed because nothing else changed).

## Known behaviour changes the client will notice
- Everything needs login by **mobile number + password**; first login of a new user forces a password change; **no idle logout** (user's decision), cookie max 30 days.
- 5 wrong passwords from the same mobile+IP → 15 minute lock, **same for everyone** (no shorter lock for Developer — a different message/time would reveal which numbers are Developer accounts). An Admin / Developer can unlock from the Users screen (this also clears the change-password lock). Extra guard: **40 wrong logins from one IP (any numbers) → that IP is locked for 15 minutes**, so an office behind one NAT IP shares that budget; the real client IP must reach the app (ProxyFix is on outside dev).
- **Logout ends the session everywhere** for that user (all their cookies stop working), not only in that browser. Changing the password does the same.
- CLI commands (`create-developer`, `reset-password`, `unlock-user`) refuse to run unless `ERP_SECRET_KEY` is set properly (they would otherwise hash/HMAC with a weak key).
- Password rule: 10+ characters (max 128), not blank, at least 5 different characters; a temporary password is always generated to pass this rule.
- Sidebar shows only pages the user may open; View-only users do not see Edit buttons; the Costing / Profit / Stock valuation pages are separate pages with their own permission; cost figures shown inside a page (e.g. unit cost on Output, Finished goods, Production order) follow that page's View level (user decision 24 Nov).
- Move / Release / Start / Reschedule of production orders now need Edit on **Production planning** (an order-entry clerk with only Production order cannot start production). Production order **expected-date preview** needs Edit on Production order.
- Demo tour (button + /demo) is Developer-only.

## Go-live checklist (before real client data — NOT part of this deploy)
- Remove the demo tour completely (`app/tour`, `static/js/tour.js`, `static/js/demo.js`, tour CSS, `DEVELOPER_ONLY_BLUEPRINTS`, base.html tags) — user decision 23 Nov.
- Remove the `claude_deploy` key from `/root/.ssh/authorized_keys`, rotate the root password (old reminder).
- Confirm the audit log shows login_ok / user_created rows and no full mobile numbers.
