#!/bin/bash
# Wire Soldering ERP — PHASE 0 (login + roles) update. NOT RUN YET (user ne deploy nahi bola). Pehle beta / staging par check karna.
# Purane update_live_bundle.sh ke same steps, par login-aware:
#   0. precondition: /etc/wire-soldering.env me ERP_SECRET_KEY (>= 32 chars) — warna naya app web request refuse karta hai
#   2b. 3 naye libs (Flask-Login, Flask-WTF, WTForms) live venv me — additive, purana code inse nahi tootta
#   3. staging sweep ab login ke saath (scripts/deploy_phase0/staging_sweep.py)
#   6. health: /login 200 + bina login har page 302 (guard zinda) + [optional] ASLI login POST public hostname se + logged-in sweep
#      (login check ke liye /root/deploy_wire/health.cred banao: line1 = mobile, line2 = password, chmod 600; kaam ke baad delete karo)
# Deploy ke BAAD turant (service user se, interactive ssh -t): flask create-developer --mobile <10 digit> --name "Owner"
#   -- jab tak Developer nahi bana, koi login nahi kar sakta (app locked, data safe). Poora runbook: PHASE0_DEPLOY_RUNBOOK_2026_11_23.md
set -u
APP=/home/portal.ivinfotech.com/wire_soldering
OWNER=porta1691
V=$APP/venv/bin
TS=$(date +%Y%m%d_%H%M%S)
BK=/root/deploy_wire/backups/phase0_$TS
ST=/root/deploy_wire/stage_update
ENVFILE=/etc/wire-soldering.env
CRED=/root/deploy_wire/health.cred
PUBLIC=https://portal.ivinfotech.com
fix_owner() { find "$APP" -path "$APP/venv" -prune -o -exec chown $OWNER:$OWNER {} + ; }
as_owner() { runuser -u $OWNER -- env HOME=/home/portal.ivinfotech.com ERP_SECRET_KEY="$SECRET" "$@"; }
mkdir -p "$BK"
cd "$APP" || exit 1

# ---- 0. PRECONDITION: secret key ----
SECRET=$(grep -E '^ERP_SECRET_KEY=' "$ENVFILE" 2>/dev/null | head -1 | cut -d= -f2-)
if [ "${#SECRET}" -lt 32 ]; then echo "ERP_SECRET_KEY missing / < 32 chars in $ENVFILE (live untouched)"; exit 1; fi
echo "secret key present (length ${#SECRET}, value not printed)"

OLD_HEAD=$(git rev-parse HEAD)
echo "$OLD_HEAD" > "$BK/old_head.txt"
echo "backup: $BK   old HEAD: $OLD_HEAD"

# ---- 1. BACKUP ----
tar -czf "$BK/code_before.tgz" --exclude=./venv --exclude=./instance --exclude=./__pycache__ . && echo "code backup ok"
$V/python - <<PY
import sqlite3
src = sqlite3.connect("file:$APP/instance/erp.db?mode=ro", uri=True)
dst = sqlite3.connect("$BK/erp_before.db")
src.backup(dst)
print("db backup ok, integrity:", dst.execute("pragma integrity_check").fetchone()[0], "| alembic:", dst.execute("select version_num from alembic_version").fetchone()[0])
PY
cp -a "$APP/instance/uploads" "$BK/uploads_before" 2>/dev/null

rollback() {
  echo "!!! FAILED at: $1 -> ROLLBACK"
  systemctl stop wire-soldering
  git reset --hard "$OLD_HEAD"
  fix_owner
  cp -a "$BK/erp_before.db" "$APP/instance/erp.db"
  chown $OWNER:$OWNER "$APP/instance/erp.db"
  systemctl start wire-soldering
  sleep 3
  echo "rollback done; local check: $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:5060/units)"
  exit 1
}

# ---- 2. FETCH + ff check ----
git fetch --quiet /root/deploy_wire/wire.bundle +main:refs/remotes/origin/main || { echo "fetch failed (live untouched)"; exit 1; }
git merge-base --is-ancestor HEAD origin/main || { echo "server HEAD origin/main ka ancestor nahi (live untouched)"; exit 1; }
echo "will move to: $(git rev-parse origin/main)"

# ---- 2b. NAYE LIBS (additive; purana code inhe import nahi karta) ----
$V/pip install -q "Flask-Login==0.6.3" "Flask-WTF==1.2.2" "WTForms==3.2.1" || { echo "pip install failed (live untouched)"; exit 1; }
$V/python -c "import flask_login, flask_wtf, wtforms; print('libs ok', wtforms.__version__)" || { echo "libs import failed (live untouched)"; exit 1; }

# ---- 3. STAGING: naya code + live DB ki copy, migrate + login ke saath saare pages ----
rm -rf "$ST"; mkdir -p "$ST"
git clone --quiet -b main /root/deploy_wire/wire.bundle "$ST/app" || { echo "clone failed (live untouched)"; exit 1; }
mkdir -p "$ST/app/instance"
cp "$BK/erp_before.db" "$ST/app/instance/erp.db"
cp -a "$BK/uploads_before" "$ST/app/instance/uploads" 2>/dev/null
cd "$ST/app"
FLASK_APP=run.py ERP_DEV=1 $V/flask db upgrade > "$ST/upgrade.log" 2>&1 || { tail -8 "$ST/upgrade.log"; echo "staging migrate failed (live untouched)"; exit 1; }
echo "staging alembic: $(FLASK_APP=run.py ERP_DEV=1 $V/flask db current 2>/dev/null | tail -1)"
FLASK_APP=run.py ERP_DEV=1 $V/flask inventory-backfill > "$ST/backfill.log" 2>&1 || { tail -8 "$ST/backfill.log"; echo "staging inventory backfill failed (live untouched)"; exit 1; }
$V/python "$ST/app/scripts/deploy_phase0/staging_sweep.py" "$ST/app" || { echo "staging login sweep failed (live untouched)"; exit 1; }
cd "$APP"

# ---- 4. STOP + CODE ----
systemctl stop wire-soldering || rollback "stop"
if [ -f "$APP/requirements.txt" ] && ! git ls-files --error-unmatch requirements.txt >/dev/null 2>&1; then
  mv "$APP/requirements.txt" "$BK/requirements_untracked.txt"
fi
git merge --ff-only origin/main > "$BK/merge.log" 2>&1 || { cat "$BK/merge.log"; rollback "merge"; }
fix_owner
echo "code now at: $(git log --oneline -1)"

# ---- 5. MIGRATE (live DB, data rehti hai; users / roles / audit tables + 2 built-in roles (Developer, Admin) banti hain) ----
as_owner env FLASK_APP=run.py $V/flask db upgrade > "$BK/upgrade.log" 2>&1 || { tail -8 "$BK/upgrade.log"; rollback "db upgrade"; }
echo "alembic now: $(as_owner env FLASK_APP=run.py $V/flask db current 2>/dev/null | tail -1)"
as_owner env FLASK_APP=run.py $V/flask inventory-backfill > "$BK/backfill.log" 2>&1 || { tail -8 "$BK/backfill.log"; rollback "inventory backfill"; }

# ---- 6. START + HEALTH (login-aware) ----
systemctl start wire-soldering || rollback "start"
for i in 1 2 3 4 5 6 7 8 9 10; do
  [ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:5060/login)" = "200" ] && break
  sleep 2
done
FAIL=0
[ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:5060/login)" = "200" ] || { echo "login page not 200"; FAIL=1; }
# guard zinda: bina login protected pages login par bhejte hain (302), khule nahi
for P in /units /dashboard /inventory/stock /vendors /production_orders /quotations /admin/users/; do
  C=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:5060$P")
  echo "anonymous $C $P (302 expected)"
  [ "$C" = "302" ] || FAIL=1
done
[ "$FAIL" = "0" ] || rollback "health check (guard)"

if [ -f "$CRED" ]; then
  MOBILE=$(sed -n 1p "$CRED"); PASSWORD=$(sed -n 2p "$CRED")
  JAR=$(mktemp)
  TOKEN=$(curl -s -c "$JAR" "$PUBLIC/login" | grep -o 'name="csrf_token" value="[^"]*"' | head -1 | sed 's/.*value="//; s/"$//')
  LOGIN=$(curl -s -b "$JAR" -c "$JAR" -o /dev/null -w '%{http_code}' --data-urlencode "mobile=$MOBILE" --data-urlencode "password=$PASSWORD" --data-urlencode "csrf_token=$TOKEN" "$PUBLIC/login")
  echo "real login POST via $PUBLIC: $LOGIN (302 expected)"
  [ "$LOGIN" = "302" ] || FAIL=1
  for P in /dashboard /units /inventory/stock /opening_stock /inventory/valuation /stock_transfers /stock_adjustments /material_issues /production_orders /production_planning /costing /quotations /dispatch /invoices /receipts /sales_profit /sales_returns /customer_statement /receivables /routing /production_output /purchase_orders "/purchase_orders?tab=completed" /grns /inward_qc /purchase_invoices /purchase_returns /vendors /raw_materials /admin/users/ /admin/roles/ /admin/access/ /admin/audit/; do
    C=$(curl -s -b "$JAR" -o /dev/null -w '%{http_code}' "$PUBLIC$P")
    echo "logged-in $C $P"
    [ "$C" = "200" ] || FAIL=1
  done
  rm -f "$JAR"
else
  echo "NOTE: $CRED not found -> real login check SKIPPED (create it to test login end to end)"
fi
[ "$FAIL" = "0" ] || rollback "health check (login)"
systemctl is-active wire-soldering
journalctl -u wire-soldering --no-pager -n 4 | cut -c1-180
echo "PHASE0 UPDATE OK  backup=$BK"
echo "NEXT: ssh -t ... runuser -u $OWNER -- env FLASK_APP=run.py ERP_SECRET_KEY=... $V/flask create-developer --mobile <10 digit> --name Owner"
