# Accounts A2: command line tools. "flask accounts-backfill" (purane party balances ko Opening voucher me) aur "flask accounts-tally" (farak dikhao).
from datetime import datetime

import click

from app.extensions import db


def register_cli(app):
    @app.cli.command("accounts-backfill")
    @click.option("--date", "on_date", default=None, help="Opening voucher ki date (YYYY-MM-DD). Khali = aaj.")
    def accounts_backfill_command(on_date):
        from app.accounts.opening import backfill
        day = datetime.strptime(on_date, "%Y-%m-%d").date() if on_date else None
        made, skipped = backfill(voucher_date=day)
        db.session.commit()
        print("Accounts backfill done: %d opening voucher(s) made, %d ledger(s) skipped (already match the vouchers)." % (made, skipped))
        from app.accounts.fixedcost import backfill as fixed_cost_backfill
        fixed = fixed_cost_backfill()          # purane outputs ka fixed cost voucher (jo pehle se ban chuke unhe nahi chhoota)
        db.session.commit()
        print("Fixed cost vouchers made for existing outputs: %d." % len(fixed))

    @app.cli.command("accounts-tally")
    def accounts_tally_command():
        from app.accounts.opening import party_ledgers, tally
        rows = tally()
        print("Party ledgers checked: %d. Mismatches: %d." % (len(party_ledgers()), len(rows)))
        for ledger, from_entries, current, diff in rows:
            print("  %s: vouchers %.2f vs balance %.2f (diff %.2f)" % (ledger.name, from_entries, current, diff))
