# Deploy readiness — build phase 17 Nov 2026 (Batches 1-19)

Status: **local only. Nothing is pushed or deployed.** Deploy/push only when the user says so.

## What goes live
- 20 commits since the last live deploy (`f6ff725`, 16 Nov): `6a4b017` (Batch 1) ... `4e74164` (Batch 19). 59 files, about +3200 / -700 lines.
- Items: C1-C19 and G1-G32 of `demo_changes_2026_11_16.md` (all done or verified; see the BUILD LOG there, per batch).

## Migrations (live is at `f4b8d0c2e6a9`; new head `f1b6d3e8a4c9`)
| Revision | What |
|---|---|
| `a5c1e7b3d9f2` | order: make-extra %, short action / note (C18) |
| `b6d2f8a4c1e7` | work stage: "Counted in pieces" (C15) |
| `c7e3a9d5b1f4` | work stage: "Max wait" minutes (C12) |
| `d8f4b1c6e2a9` | machine: batch capacity + hours per batch (C8a) |
| `e9a5c2d7f3b8` | `melt_groups` table + stage.melt_group_id (C9 phase 2) |
| `f1b6d3e8a4c9` | `machine_extra_hours` table (C10) |

All additive (new columns have defaults / are nullable, 2 new tables). No data migration, no column drops.

## Verified locally (test copies only)
- Upgrade of a live-like DB (`f4b8d0c2e6a9`, 69 tables, 640 rows) to head: **0 rows lost or changed**, 2 new tables.
- Smoke: all 44 parameter-less GET pages answer without a server error; `compileall` clean; one alembic head.
- Auto-tests b4-b19 (each batch's own test + regressions) all pass.
- Not testable here: the server's Python 3.9 (local is newer). Run the staging sweep on the server (existing flow) before the real switch.
- Known and old (not from this build): `flask db upgrade` on a completely empty DB fails at the `baseline` migration (it expects tables to exist). Live is unaffected.

## Deploy method (as on 16 Nov)
1. User says "push / live karo". (Repo on GitHub is PRIVATE; never make it public.)
2. `git bundle create deploy/wire.bundle HEAD main` and run `run_update_bundle.sh`: backup -> staging on a copy of the LIVE DB (migrate + page sweep) -> ff-merge -> `flask db upgrade` -> health check -> auto-rollback on failure.
3. Live DB is NOT overwritten; live data stays.

## Live data to set after deploy (needs the user's OK; none of it is done)
- **Tin purity** "Min 100.5%" -> correct value (G29).
- **Spooling** work stage: tick "Counted in pieces" (C15).
- **Melting & Alloying**: "Max wait before next stage" minutes (C12); machines: furnace **batch capacity** + **hours per batch** (C8a).
- Flux product / recipe link, if still pending (see earlier notes).
- Scrap types such as "Test samples" / "Rejected after test" in the Scrap type master, if wanted (G16).

## Behaviour changes the client will notice
- Queue actions (Plan / Release / Start / Cancel / arrows) moved from Production order to **Production planning**; Production order page = add + status + Print.
- Material plan has 3 tabs (by production order / all materials / create purchase orders).
- A stage cannot start until its own material is fully issued (C7), the machine is free (C8), and the previous Lab test + TC is done.
- Testing / Packing in PCS once Spooling is counted in pieces (C15).
- New: heat number per melt, combine same-alloy orders in one melt, stock value at the vendor bill rate, Tomorrow's plan tab + extra shift hours.

## Still open, not code
- Remove the `claude_deploy` key from the server's `/root/.ssh/authorized_keys`; rotate the root password.
- Sales module and app login are not built (portal is open to anyone with the link).
