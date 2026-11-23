# Dashboard se machine assign + start (cross-line) — FLOW (2026-11-23)

**Status: APPROVED 23 Nov + B0–B6 BUILT, committed fba789c, LIVE 23 Nov (migration c3d9a5e7f1b4). Doc se alag: combined melt = poora group target furnace par jaata hai (refuse nahi); queue-only assign sirf Released orders ke liye.** Yeh file `tracker.md` Current Focus aur `memory.md` se linked hai.

## 1. Requirement (user, 23 Nov, "client ne bhi kaha tha")
Order 1 + Order 2 = Line 1, Order 3 = Line 2. Order 1 Line 1 ke furnace me Melting chala raha hai. Order 3 ki Melting khatam, Line 2 ka furnace FREE. Order 2 (Line 1) ko Line 1 ka furnace busy hone se start nahi mil raha. **Dashboard se hi** Line 2 ka free furnace Order 2 ko assign + start kar sakein (client: "machine ya aadmi ek minute bhi nahi baithna chahiye" — meeting 2, transcript line 133). Phir Order 2 stage 2 par kahan jayega, ye sab scenario ek flow me pehle decide ho.

**Pehle md me kya tha (sach):** `demo_changes_2026_11_16.md` line 109 — C11 *proposed*: "Dashboard machine pop-up me order/stage ko khali machine par shift... Dashboard abhi sirf queue ▲▼ deta hai — Line 2 me casting bhejne ka option abhi nahi hai (nahi bana)". Line 123 (AGREED C8+C11+G14) me sirf stage **Start par "Use this machine instead"** aaya, dashboard wala hissa agreed list se chhoot gaya, aur dobara uthaya nahi gaya. Spec 28.1: "Moving an order to another line stays possible".

## 2. Abhi kya hai (verified, DB copy par chalakar)
- Routing page par stage Start: planned machine busy ho to "Use this machine instead" me kisi bhi line ki free machine (same stage) milti hai. Order 2 ki Melting Furnace 2 par start ho jati hai. **Ye kaam karta hai.**
- Dashboard: sirf dekhna + Released order ka queue ▲▼. Assign / Start button **nahi**. Furnace 2 idle dikhta hai jabki Order 2 intezaar me — koi signal nahi ("idle machine, waiting order").
- Agla stage: har stage apni **planned machine** par jata hai (Order 2 ka Casting = Line 1 ki Casting Machine 1). Wo free ho to seedha start; busy ho to wahi swap option (kisi bhi line ki free machine).

## 3. Flow rules (proposed — ye decide karne hain)
1. **Line = order ka "home" label; machine = asli resource.** Har stage same work-stage ki kisi bhi Active machine par chal sakta hai, kisi bhi line ki. `order.line_id` home line rahegi (planner filter, order Start ka capacity rule, label).
2. **Dashboard idle tile:** machine Active + koi stage running nahi + hot metal incoming nahi => tile par **"Idle — PROD-002 (Line 1) waiting"** + button **Start here**.
3. **Assign & Start (ek hi form, ek transaction):** operator, time, aur jo reasons maange (clash / re-wait / furnace not full / casting-ahead). Agar order abhi Released hai to pehle order-level Start (home line + under-capacity reason) phir stage Start. **Wahi code path jo Routing page ka hai** — koi gate bypass nahi (material issued, Lab QC TC, previous stage Done, machine status, busy, hot-metal).
4. **Kaun order milega (jab kai wait kar rahe):** Ready (material + TC ok) -> queue position -> needed-by date. Manager doosra order chun sakta hai (reason stage notes me). Agar us machine ki apni line ka order uske queue me aage ho, to warning + reason.
5. **Agla stage (user ka 2nd sawal):** Order 2 Melting Line 2 ke furnace par kare, phir Casting par **apni planned machine (Line 1 Casting Machine 1)** par jayega agar free hai (Order 1 abhi Melting me hai, to free hai) — bina kuch kiye. Agar wo busy / Order 1 ka hot metal aane wala hai => hot-metal clash warning + dashboard ke Casting idle tile par bhi "Start here" (kisi bhi line ki machine) wahi flow. Kuch auto-reroute nahi hota; manager decide karta hai.
6. **Hold:** On-hold stage ki machine busy rehti hai (metal andar hai), koi dusra order nahi le sakta.
7. **Breakdown / maintenance machine:** offer nahi hoti (already). Start ke baad kharab ho to Hold / Cancel run / dusri machine se restart (already).
8. **Combined melt (same alloy heat group):** first cut me cross-furnace assign **refuse** (message: group ki saari members ek saath move honi chahiye); baad me poora group ek saath move.
9. **Do manager ek saath:** write ke waqt machine ka busy dobara check (race).
10. **Record:** planned machine delete nahi hogi; naya `production_order_stage_machine_changes` log (stage, from, to, kind, reason, time). Cancel run par planned machine wapas. Order screen / pop-up par **"Home: Line 1 · Melting on Line 2"**.
11. **Line Status / capacity:** home line par hi rahega + informational "lent/borrowed" text; block nahi. Costing/output/variance/scrap par koi asar nahi (machine/line nahi padhte).
12. **Permissions:** Phase 0 (roles) ke baad sirf Production manager. Abhi koi login nahi.

## 4. Scenario table
| # | Scenario | Result |
|---|---|---|
| 1 | Owner case: apna furnace busy, doosri line ka free | Dashboard idle tile "Start here" -> Order 2 Furnace 2 par chalta hai |
| 2 | Dono lines ki machine busy | Start disabled, dono ka "free about HH:MM" dikhta hai |
| 3 | Dono free | Planned machine hi (auto-pick nahi) |
| 4 | Kai orders wait | Ready -> queue -> needed-by; manager override + reason |
| 5 | Free machine ki apni line ka order uske queue me aage | Warning + reason |
| 6 | Order 2 ka stage 2, apni line ki Casting free | Seedha start (Order 1 ka hot metal aane wala ho to clash reason) |
| 7 | Stage 2, apni busy, doosri line ki free | Casting idle tile par Start here / Routing swap — same flow |
| 8 | Stage 2, sab busy | Wait; hot metal timer (C12) chalta rahe |
| 9 | Hot metal clash (target machine par) | Target machine par check (abhi planned machine par hota hai — fix zaroori) |
| 10 | Target machine breakdown | Offer nahi |
| 11 | Stage On hold | Machine busy, koi nahi le sakta |
| 12 | Lab QC TC pending / material issued nahi | Start disabled + reason (same gate) |
| 13 | Furnace batch capacity alag | Chuni hui machine ke numbers se lots / waste check / hours |
| 14 | Combined melt | First cut refuse |
| 15 | Flux order (Flux Mixers, Line 3 bhi) | Same flow, line capacity skip (already) |
| 16 | Start ke baad undo | Cancel run -> planned machine wapas (log se) |
| 17 | Running stage ko doosri machine par | Nahi; Cancel run + restart |
| 18 | Order cancel while running | Pehle Stop (already) |
| 19 | Do manager same machine | Dusre ko "ab busy" |
| 20 | Line off (switched off) par machine | Offer nahi (abhi offer ho jati hai — fix) |
| 21 | Machine queue me daalna bina start (client ka queue idea) | Phase 2: in-place row edit + persist (verified safe) |

## 5. Build se pehle jo bugs/fix (research me mile)
- **D1 (high):** swap ke baad stage purani machine ke numbers (capacity/planned_hours) use karta hai; waste check bhi purani furnace par. -> effective machine par recompute.
- **D2 (high):** combined melt + swap: member order purani (busy) furnace par running dikhta hai, Furnace 1 double-booked. -> rule #8.
- **D3 (medium):** scheduler: Done stage ki machine planned end tak busy maani jati hai, to Furnace 2 idle hone par bhi naya order 25 Nov dikhta hai (fake idle). Done stage ko completion par machine chhodna; In-progress `max(planned end, today)`.
- **D5:** hot-metal clash swap target par nahi, planned machine par check hota hai. **D6:** line off ho to bhi machine offer. **D7:** planned row delete (history sirf note me, 255 char).
- Voluntary swap ignore hota hai (planned free ho to swap_machine_id padha hi nahi jata) -> explicit target machine param.
- Pehle wala bug: `_save_plan` ke baad `order.stages` stale (ek line `db.session.expire(order, ["stages"])`) -> persisted stage dates galat.
- `routing_start` ke gates inline hain, reuse function nahi: `start_stage(...)`, `start_order(...)`, `start_blockers(...)`, `eligible_orders_for_machine(...)` extract karne honge (Routing page ka behaviour wahi rahe).

## 6. Build order (har step: concept -> auto-test -> user ko live demo)
- **B0** stale-stages one-line fix + test.
- **B1** helpers extract (no behaviour change) + purane tests pass.
- **B2** effective-machine fixes (D1, D5, D6, explicit target) + change-log table (migration) + Cancel-run restore.
- **B3** scheduler: early release of Done stage machines (D3).
- **B4** Dashboard idle tile + "Assign & Start" drawer (Melting, Casting, baaki stages) + "Home: Line 1 · Melting on Line 2".
- **B5** combined melt refuse + race re-check.
- **B6 (phase 2)** "Assign to queue" bina start.

## 7. Open questions (user se)
1. Sirf "Start here now" pehle (B1-B5), queue me daalna (B6) baad me — theek?
2. Free machine ki apni line ka order uske queue me aage ho, to dusri line ka order le sakta hai? (rec: haan, reason ke saath)
3. Released (abhi In production nahi) order ko bhi dashboard se assign + start? (rec: haan, order Start saath me)
4. Borrowed machine par Line 2 ke handler ko approval chahiye ya sirf info? (rec: sirf info)
5. Home line ka under-capacity reason order Start par hi rahe? (rec: haan)
