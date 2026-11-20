# Fix list — jo cheezein app me theek karni hain

Yeh list full-flow demo (18 Nov 2026) ke dauran mili. Abhi kuch fix nahi kiya gaya, sirf note hai. Har point ke saath likha hai ki kahan dikha aur kya hona chahiye.
Fix karne se pehle user se confirm karna (CLAUDE.md rule: pehle poocho, guess mat karo).

## Production / Packing

1. **Chhote order ke liye poora box lag raha hai.**
   - Kahan: 7 pcs ke balance order me Material issue ne 1 Corrugated Box Medium (25 KG / 50 pcs wala box) issue kiya. Box ka poora cost 7 pcs par chadh gaya.
   - Kya hona chahiye: box ki cost pcs ke hisaab se bante (7/50 box), ya bacha hua box store me wapas jaye. Decision chahiye ki kaunsa tarika.
2. **[FIXED 20 Nov 2026 (user: "tick on-off ka sawal hi nahi, unit conversion stage hona chahiye"), local only, live par deploy baaki; auto-test 63/63 (real forms Spooling -> Testing -> Packing in PCS)] Spooling ke baad quantity PCS me honi chahiye, KG me nahi — YEH CODE ME PEHLE SE BANA HAI (C15, 16 Nov), bas master data me tick nahi laga.**
   - Kahan: Testing & QC aur Packing ke "Complete stage" form me "Came into this stage" aur "Good output" KG me dikhte hain.
   - Asli wajah: Work stages master me Spooling par "Counted in pieces (PCS) from this stage" ka tick (`work_stage.counts_pcs`) 0 hai. Real local `instance/erp.db` aur demo DB dono me 0 mila. Tick lagate hi Spooling form "Spools made (PCS)" maangega aur Testing/Packing PCS me chalenge (demo_changes_2026_11_16.md C15, DEPLOY_READINESS_2026_11_17.md).
   - Kya karna hai: Spooling par tick lagana (aur live deploy ke baad bhi, deploy note me likha hai). Ho sake to migration/seed me default tick bhi daalna, taaki bhoolne par KG wala purana behaviour na chale.
3. **Balance order ki default quantity sirf kami jitni (7 pcs) bharti hai.**
   - Kahan: Production orders → Completed → "Make balance order".
   - Problem: scrap aur correction ki wajah se exact 7 banane par hamesha kam hi padta hai (demo me 6 bane).
   - Kya hona chahiye: user ko bada batch (jaise 20 ya 50 KG) banane ki suggestion/option mile, jisme extra maal stock me jaye aur baad ke orders usi se dispatch ho.

## Lab test / correction

4. **[BUILT 20 Nov 2026, auto-test 46/46 (t3_fx, #4+#5+#7 saath) + purani chain pass] Correction me jo extra metal dala, woh agle stage ke input me nahi judta.** Fix: lab correction (Done stage par) ab us stage ka `qty_in`/`qty_out` badhata hai, to agle stage ka "material in" = pichla output + correction; routing form me "(includes X KG correction (Tin) added at Melting)" line. Agla main stage start ho chuka ho to correction refuse (message). `routing/routes.py` (`correction_in`, `next_main_stage`, `routing_lab_qc`).
   - Kahan: Melting ke lab test me 0.5 KG Tin add kiya, par Ingot Casting me "material in" 3.5 KG hi raha. Cost badhi (Tin 2.6 KG used) par output nahi badha.
   - Kya hona chahiye: batao ki correction ka metal agle stage ke weight me jude, ya alag se dikhe.

## Scrap

5. **[BUILT 20 Nov 2026, auto-test 46/46] Scrap sab stage me record nahi hota.** Fix: Work stage master me positive tick "Scrap can be recorded at this stage" (default ON, sab stages par — Extrusion/Wire Drawing bhi); migration `a1e6c3d8f2b7` purane sab stages par scrap allowed kar deta hai; untick karne par server scrap 0 karta hai; billet stage hamesha scrap-allowed.
   - Kahan: Extrusion aur Wire Drawing me "No scrap is recorded at this stage". Scrap sirf Spooling aur Testing/Packing me daal sakte hain.
   - Kya hona chahiye: user ko batana ki scrap kahan daalna hai, ya in stages me bhi scrap ka option ho.

7. **[BUILT 20 Nov 2026 (safe gate, auto-test 46/46): chalta hua (In production) order ab cancel ho sakta hai agar: koi Posted output nahi, koi stage In progress / On hold nahi, aur issue kiya gaya sab material wapas (return) aa chuka ho. Warna message "pehle material return / output cancel / stage stop karo". Planning page ke In production card par "Cancel order" button. Pura cancel (finished order beyond gate) abhi nahi.] [Purani note — 20 Nov 2026 CHECK: DRAFT / RELEASED order ka cancel PEHLE SE BANA HAI (`/production_orders/cancel/<id>`, reason zaroori, material issue ho to roke). Test: quotation se bana Draft PO cancel kiya, quotation / dispatch / planning / invoices / profit pages 200 OK. Baaki gap sirf neeche wala: chala hua (In production / 9 of 9 stages) order cancel nahi hota — risky (material issue, output, FG batch, dispatch tak), abhi chhoda; 11/12 ke baad dekhenge.]** Galat/bekaar chali hui production order ko hatane ka koi rasta nahi.
   - Kahan: PROD-2026-002 (stages 9/9 done) ke ⋯ menu me sirf "Routing / stages" hai, Cancel order nahi. Sirf "Cancel output" (Production output → Recorded) milta hai, jo order ko wapas "In production" kar deta hai.
   - Kya hona chahiye: decide karna hai — kya aise order ko cancel karne ka option ho (issued material wapas karke / write-off karke), ya sirf close-as-is. CLAUDE.md rule: hard delete nahi, sirf cancel/reverse.

8. **Packing me box-wise pcs record nahi hote.**
   - Kahan: PROD-2026-002 (73 pcs) me Packing form sirf "2 BOX used" leta hai, aur sirf average dikhata hai (36.5 pcs/box, ≈18.25 KG). Box ki capacity 25 KG / 50 pcs hai, asli packing 50 + 23 hogi, par yeh kahin save nahi hota.
   - Kya hona chahiye: decide karna hai: box-wise pcs record hon (Box 1 = 50, Box 2 = 23), ya sirf total box + average rahe. Dispatch / challan par box count ya per-box pcs chahiye ya nahi, yeh bhi poochna hai.

9. **[FIXED 20 Nov 2026 (user: "haan fix kar"), auto-test 11/11 + purani fresh-DB chain 105/105, 97/97, 52/54 (2 = test ki galti), s1–s12 pass] Ek hi din ke 2 batch par fixed cost din ke ₹2,400 se zyada lag raha hai (costing).** Fix: `app/costing/fixed.py restate_day()` — output record ya cancel hone par us din ke saare 'Approx' output ek common per-KG rate (din ka kharcha / din ka total KG) par restate; 'Final' kabhi nahi chhue jaate; `production_output/routes.py` cancel par bhi.
   - Kahan: Costing → Batch cost (18 Nov). Fixed day cost ₹2,400, par batch 1 (93 pcs, 46.5 KG) ko poora ₹2,400 mila (₹25.81/pc) aur batch 2 (73 pcs, 36.5 KG) ko din ke 83 KG me se apna hissa (₹14.46/pc = ₹1,055). Kul ₹3,455.42 > ₹2,400.
   - Wajah (andaza): "recorded batch kabhi change nahi hota" rule ki wajah se pehla batch poora din le leta hai, doosra batch baad me bante waqt din ke total KG par hissa leta hai. Months tab me month finalise hone par theek hota hai ya nahi, yeh check karna hai.
   - Kya hona chahiye: same din ke batch milke din ke ₹2,400 se zyada na lagayen (ya finalise ke baad sahi baantein). Decide karna hai.
   - **[20 Nov 2026 RE-TESTED on fresh DB, independent raw-SQL check]:** dobara confirm — same din (9 Nov) ke 2 output: pehle ko ₹2,400 (₹96/KG), doosre ko ₹709.86 (₹67.61/KG) => din ka total ₹3,109.86 > ₹2,400, dono ka rate alag. **Month finalise ke baad theek:** sab output ek hi final per-KG rate, kul fixed = final amount exact (₹66,000 test me) — yaani problem sirf 'Approx' wale beech ke time me hai (profit/loss gate us time kuch zyada kharcha dikhata hai). Fix option (user decide kare): same din ka naya output aaye to usi din ke pehle 'Approx' output ko bhi naye common per-KG rate par restate karo (Final wale kabhi nahi).
10. **Balance order ka note "Balance order PROD-2026-002 for 7 PCS" galat dikhta hai jab order 80 pcs ka banaya.** Completed tab me PROD-001 ke niche note shortage (7) dikhata hai, asli order quantity (80) nahi.

## User ke 4 findings (18 Nov 2026) — user ne kaha "haan, likho"; DESIGN agreed, BANANA abhi baaki (ek-ek step, user ke "aage badho" par)

Yeh 11–13 production + dispatch + quotation ka flow badalte hain; 14 invoice ka. Pehle purane decisions se clash check kiya (neeche har point me).

11. **[REDESIGNED + BUILT 20 Nov 2026 (final design, user ne "haan" kaha), auto-test 46/46 + purane 57/57 on DB copy; demo baaki] PO Draft me khule, REVIEW Production order form me, phir plan, phir release.**
    - **FINAL design (ye chalta hai):** (1) **Extra % = extra PIECES.** `planned_qty = customer qty x (1 + extra%/100)`, pieces me upar round, KG me 2 decimal (`app/production_orders/extra.py`). Metal recipe se apne aap judta hai; purana "metal-only extra" (C18 `extra_factor`) HATA diya. **Scrap / wastage ka cushion SIRF material-wise Spare %** (order form ka raw material table; bacha spare store me wapas). (2) Extra pieces FG me **unreserved Extra stock** (dispatch use kar sakta hai); "Short" card tabhi jab good < customer qty. (3) **Production order form me "Made for"**: Against quotation (QT picker, sirf QT number — party ka naam nahi; qty = customer qty readonly; extra pieces sirf Extra % se) ya Stock order (no quotation) (qty free, extra nahi). Quotation chuni to `QuotationLine.production_order_id = order.id` (naya link column nahi); line kisi chalte PO se judi ho / pura dispatch ho chuka ho to picker me nahi aati. (4) **Finalize se bana PO "Needs review"** (`ProductionOrder.reviewed = False`, migration f8c3e0a4b6d5): Plan aur Release server par band jab tak **wahi Production order form (review mode, `?review=<id>`) me "Confirm order"** na dabe (`POST /production_orders/review/<id>`: extra %, spare %, other materials, dates, remarks, stock order me qty; recipe + packing dobara nikalti hai, plan dobara). Form se bane orders `reviewed=True`. (5) **Product master field "Extra % (extra pieces)"** = form, Finalize aur review ka default. Plan drawer me ab sirf line / machines / earliest start / needed by (extra box, learned-loss hint hata).
    - **Files:** `production_orders/extra.py` (naya), `source.py` (`line_needs_order`, `open_quotation_lines`), `routes.py` (`build_order(reviewed=)`, `_read_made_for`, `_add_other_materials`, `review_payload`, `production_orders_review`, gates in reschedule / release), `quotations/routes.py` (Finalize: planned qty + reviewed=False), `production_orders.html` (Made for, extra pieces, review mode), `production_planning` route + template (Needs review chip, Review order button), `production_output` (limit me extra dobara nahi), `products` (label). Tests: `scratchpad/inv14/test_po_review.py`.
    - Purane orders: C18 wale orders me `extra_percent` ka matlab "metal for scrap" tha; migration unhe badalti nahi (wo orders jaise hain, extra pieces nahi mane jaate).
    - **PURANA design (REPLACED, ab nahi hai):** Plan drawer me "Quantity to make" / drawer me Extra % for scrap + learned-loss suggestion:
    - (purana) Kya bana: Production planning ke Plan / Reschedule drawer me "Quantity to make" (customer qty se kam nahi; zyada ho to fark = extra jo FG stock me jaata hai; sirf jab koi material issue na hua ho). Recipe + packing ki zaroorat naye batch KG se dobara nikalti hai, plan ke ghante bhi. Suggestion: pichhle completed orders ke average loss se ("make about 22") + "Use 22" button; planner badal sakta hai (user ka faisla 20 Nov). Order cards par "customer needs X, extra Y goes to stock". `short_info` ab customer ki qty se kami naapta hai (planner ne extra banane ko planned_qty badhaya ho to galat "extra" nahi).
    - Files: `app/production_orders/source.py` (naya), `routes.py` (`resched_data`, `production_orders_reschedule`, `material_untouched`), `yield_info.py`, `_queue_modals.html`, `_queue_js.html`, planning route + templates. Migration nahi.
    - Baaki (iske saath nahi hua): Finalize par "PO banao / Stock se serve karo" option → #12/#13 ke saath. Draft/Released PO cancel pehle se hai (#7 check).
    - Test: `scratchpad/inv14/test_po_qty.py`.
    - Abhi: Finalize par PO Draft ban jata hai (release alag step hai), par qty quotation wali hi bhar jati hai. Kitna banana hai / extra banana hai ya nahi, yeh sochne ki jagah nahi. Demo me 66 pcs extra stock me the, phir bhi PROD-003/004 draft ban gaye aur ab latke hain.
    - Chahiye: PO par "Order qty" (quotation wali) aur "Planned / make qty" alag; fark = extra (scrap ka cushion ya stock). Release se pehle planner use khole aur qty tay kare. Extra maal PO close hone par in-house (free) stock ban jaye.
    - Saath me zaroori: Draft PO ko cancel karne ka rasta (fix_list #7 yahin judta hai), warna "stock se serve karo" wale quotation par bekaar drafts jama honge.
    - Clash check: C1 (PO page = sirf order add Draft, planning factory manager ka planning page par) — yeh usi direction me hai, clash nahi. C18 (expected loss %, order = ordered/(1-loss), "Make balance order") — overlap: C18 loss % se material nikalta hai; yeh point planner ko qty badhane ka seedha control deta hai. Dono saath chal sakte hain; decide: planned qty ka suggestion C18 ke loss % se aaye ya manual. Tolerance % (C18) wala logic planned vs order qty ke saath dobara dekhna.
12. **[BUILT 20 Nov 2026, auto-test: #11 wala 23/23 + finalize 13/13 on DB copy; demo baaki] PO ke 2 type: "Against quotation" ya "In-house stock".**
    - Bana: har order card (Production planning + Production orders) par chip "For QT-2026-00X" (party ka naam nahi — plant ko party nahi dikhti) ya "In-house stock". Type naya column nahi: quotation line link se nikalta hai (balance order original ke quotation ka). Production page ke form se bane order = In-house.
    - Against quotation: PO par quotation ka reference (QT-id), quotation page par PO link (pehle se hai).
    - In-house stock: koi quotation nahi, sirf stock banane ke liye (reason / note).
    - Finalize par 2 raste (BANA): Finalize drawer me har line par "Goods come from" dropdown: [Make (production order)] ya [In-house stock · N available]. Stock chuna to us line ka PO nahi banta (line.production_order_id khaali), bundle sirf banne wale POs ke liye; stock qty se kam ho to error "only N is in stock" aur kuch save nahi. Quotation detail me wahan "From stock" dikhta hai. Files: `app/quotations/routes.py` (`finalize_context`, `quotations_finalize`), `_finalize_drawer.html`, `quotation_detail.html`. Test: `scratchpad/inv14/test_finalize_stock.py`.
13. **[BUILT 20 Nov 2026, auto-test 21/21 on DB copy + drawer browser check; demo baaki] Dispatch me maal ka source choose ho (default auto: apna maal pehle, phir extra).**
    - Kya bana: Dispatch drawer me har line par "Choose batches": har batch (made for QT-x / in-house, kitna stock) par "Send from this" qty. Apna batch / in-house = bina reason; doosri quotation ka "Kept for QT-y" maal = reason zaroori (drawer me reason box tabhi dikhta hai), aur wo sirf line ke pending balance tak. Ek batch pick bucket me tut sakta hai (jaise 29 free + 6 borrowed = 2 challan lines). Purana qty_ auto form chalta rahta hai.
    - Data: `delivery_challan_lines` me 3 nayi columns `source_kind` (own/free/borrowed), `borrowed_from_quotation_id`, `borrow_reason` — migration `d6a1c8e2f4b3` (purani rows: from_own_order False -> free). Code: `app/dispatch/stock.py` (`split_pick`, `create_challan(picks=, borrow_reason=)`, `lent_out`), `routes.py` (`_batch_choices`), `dispatch.html`.
    - Donor quotation: reserved ghat jata hai to wahan "ready" apne aap kam dikhta hai (short) + To-dispatch row par note "N X of this order's goods went to QT-y (DC-…, reason) — shows as short here". Dispatched tab par "Goods of QT-y (reason)". Challan cancel = maal wapas, note hat jata hai.
    - Cost: challan line batch ki cost freeze karti hai (confirmed in test) — koi badlav nahi. Owner approval Phase 0 (roles) ke baad; abhi reason + record.
    - Test: `scratchpad/inv14/test_dispatch_src.py`. Purana (design) niche.
    - Default: is quotation ke apne PO ka batch.
    - Ya: in-house / extra stock se.
    - Ya: kisi DUSRE quotation ke PO ka bacha/reserved maal — reason zaroori (jaise "Admin ne kaha"). Wo donor quotation phir "short" dikhe; log me rahe kisne, kab, kis batch se, kis reason se. Roles Phase 0 me aate hain, tab tak sirf reason + log; baad me Owner approval.
    - Bina-PO quotation: stock se seedha dispatch (point 12 ka dusra raasta).
    - Cost: batch cost batch ke saath chalti hai; jis batch se gaya uski cost profit me lagegi (user se is par confirm baaki — suggestion: koi badlav nahi).
    - Clash check: C18 "Cover from stock" (FG stock + batch dikhe) pehle bana tha, par uska "real FG stock reserve" chhoda gaya tha — yeh point wahi reservation poora karta hai. Abhi "extra stock = kisi order ke liye na rakha hua stock" rule hai; naya rule usko badlega, dispatch tests dobara chalane honge.
14. **[BUILT 20 Nov 2026, auto-test 23/23 on DB copy; demo baaki — user: sab changes ke baad ek saath flow demo] Invoice ke charges editable + naya add ho (quotation / purchase invoice jaisa).**
    - Kya bana: invoice drawer me "Charges" table (dropdown Charges master se, amount, Add/Minus, + Add charge, row remove). Files: `app/sales_invoices/billing.py` (`create_invoice(..., charges=None)`), `routes.py` (`parse_charges`, drawer data me charge_id), `invoices.html`. Migration nahi (table `sales_invoice_charges` pehle se). Form me charge_count na aaye to purana default (quotation ke charges pehle invoice par).
    - Test: `scratchpad/inv14/test_inv_charges.py` (edit, naya, minus, sab hata do, khaali row, galat input, dusra invoice, ledger, print).
    - Abhi: invoice ke charges quotation se copy hote hain, read-only, aur sirf us quotation ke PEHLE invoice par (code: `app/sales_invoices/billing.py` ~line 102-113, drawer `invoices.html`).
    - Chahiye: invoice drawer me charges ki table: Charges master se dropdown, amount editable, effect Add / Minus, "+ Add charge", row remove. Default me quotation ke charges bharein (pehle invoice par), user badal / hata / naya jod sake. Totals + GST live badle.
    - GST rule purana hi rahe (decision 2026-10-16 F9): charge items ke value-anupaat me lines me baant ke har line ke rate se tax. Print aur Profit page (charges net sales me jodte hain) isi se chalenge.
    - Loss gate: charges badalne se net sales badalta hai, to loss check dobara chale.

## Demo / test tooling (app ka hissa nahi)

6. Demo narration tab-wise chalti hai: browser me ek se zyada tab usi server par khule hon to awaaz double aati hai. Demo ke waqt sirf ek tab rakho.
