# Project Memory — Decisions & Reasoning Log

Yeh file **kyun** wala context store karti hai — jab bhi koi bada decision liya jaaye (tech stack, workflow, naming, structure), yahan likhna hai taaki 6 mahine baad bhi yaad rahe "yeh aisa kyun kiya tha."

`tracker.md` batati hai **kya** hua aur **kab**. `memory.md` batati hai **kyun** hua.

---

### Decision: Product Master = ek screen, teen tables (recipe variant pe)
**Date:** 2026-09-30
**Kya:** Add Product ek hi form, 3 sections. (1) Basic details → `Product` (code, name, category, unit, HSN, tax). (2) Specs → **ek default** `ProductVariant` (`attributes` JSON: alloy grade, thickness, flux %). Alag variant-list UI nahi. (3) Recipe → naya `VariantRecipeItem` (`variant_id`, `raw_material_id`, `line_type` jaise Base Metal / Core Flux, `ratio_percent`). Base metals ka total 100% hona chahiye; flux us 100% ke bahar apna % hai.
**Kyun:** Client flow alloy product hai (Tin 60 / Lead 40 / Flux 2). Purana Product+Variant hataane ki zaroorat nahi — BOM/Sales baad me variant pe hi latke hain. Recipe alag table isliye, taaki percent lines query ho saken. Sales Order pe `qty × ratio%` se RM nikalna, phir Production Order / issue slip — woh Phase 4/6 ka kaam hai, is form ke saath nahi banega.
**How to apply:** Naya product save = Product + 1 variant + recipe lines, ek transaction. Purane multi-variant rows DB me reh sakte hain; naya form unhe nahi banata. Recipe se pehle RM Master pe do optional flags: `is_base_metal`, `is_core_flux` (default False). Dono off chal sakta hai (normal RM). Ek waqt pe sirf ek on — base metal aur core flux saath nahi. Product recipe dropdown mein sirf ticked RM aayenge. `line_type` aur "alag variant-list UI nahi" neeche 2026-10-01 decision se update ho gaye — wahi follow karo.

### Decision: Recipe lines ka exact shape + edit rule (2026-10-01)
**Date:** 2026-10-01 (upar wale 2026-09-30 decision ka implementation detail)
**Kya:**
- Column `line_type` nahi bana. `VariantRecipeItem` pe `ratio_percent` + `is_flux` (Boolean). `is_flux` RM ke `is_core_flux` se copy hota hai save ke waqt.
- Base metals ka total 100%. Flux us 100% ke bahar apna ratio hai.
- Specs fixed Alloy/Thickness fields nahi — wahi dynamic attributes (`attr_key_0[]` / `attr_value_0[]` add product pe; variant modal pe `attr_key[]` / `attr_value[]`).
- Product list pe variant rows rehte hain (expand). Recipe usi table ki child rows hain, alag card nahi. Add Product ek default variant banata hai (`{name}-Standard`, sku `{code}-STD`). Extra variant Add/Edit ab bhi hai.
- Flow check (order qty → kitna material) sirf screen pe hai, save nahi. Unit KG/KGS ho to weight = 1. Warna order qty × weight-per-unit (KG) × ratio/100.
- Recipe edit = us variant ki purani `VariantRecipeItem` rows **hard-delete** karke nayi insert. Variant khud soft-delete rehta hai. Safe hai kyunki koi document abhi in rows ko FK se point nahi karta.
- Aage Sales/Production order pe ratios **copy** honge document pe. Recipe line ki id FK mat banana — master formula badlegi to purana order nahi badlega.

**Kyun:** Client alloy formula (Tin/Lead/Flux) master pe rakhta hai, lekin shipped order ki recipe us din ki honi chahiye. Child rows hard-delete isliye theek hai; business document soft-delete rehta hai.

**How to apply:** `products_add`, `products_variants_add` (naya + deleted-SKU restore), aur `products_variants_edit` recipe save karte hain. **Product edit mein recipe / attributes mat daalo** — list pe standard variant ka Edit button wahi kaam karta hai. Product edit sirf header: code, name, category, description, unit, HSN, tax. Toggle/delete routes recipe mat chhedo.

### Decision: Master code auto, edit pe regenerate nahi (2026-10-01)
**Date:** 2026-10-01
**Kya:** Charges jaisa serial code baaki masters pe bhi, ek-ek karke. Pattern: last row `id + 1`, prefix + 4 digits (`CHG-0001`). Form se code mat lo — route khud generate kare. Edit pe purana code rehna chahiye, naya number mat banao.
**Product:** code auto `FG-0001`. Default variant SKU auto `{code}-STD` (user SKU type nahi karega). Extra variant SKU `{code}-02`, `{code}-03` — us product ki variant rows count karke, deleted rows bhi count, taaki SKU dubara na bane.
**Mat auto karo:** Unit (`KG`, `ROLL`) aur Tax Rate (`GST18`) — wahan code ka matlab hai, serial nahi. HSN bhi user ka hai, government code hai.
**Kyun:** User ne Charges pe auto code dekh ke sab masters pe wahi maanga. Product code aur variant SKU alag counters nahi — SKU product code se judi rehti hai, warna `FG-0007` ka variant `VAR-0012` ho kar link toot jaati hai.
**How to apply:** Pehle Product (code + dono SKU rules). Phir RM, category, machine, warehouse, vendor, customer. Unit aur Tax Rate chhod do.

---

### ⚠️ SUPERSEDED (same din baad me) — Product pe GST slab abhi nahi
**Date:** 2026-09-23 (superseded 2026-09-23, neeche naya decision dekho: "Tax Rate Master banega")
**Kya tha:** Product form se hardcoded Tax dropdown hata diya tha, `tax_rate` column unused chhod diya tha, socha tha HSN/Tax master baad me (Sales/GST phase me) banega.
**Kyun ulta hua:** Usi din baad me user Product Master pe kaam karte waqt HSN/tax_rate field ke role ko leke confuse hua — poora tax flow discuss karne ke baad decide hua ki **abhi** (Product Master se pehle hi) chhota Tax Rate Master bana lena better hai, kyunki spec khud rates ko admin-configurable maangta hai (hardcode/unused chhodna galat). Poori reasoning neeche "Tax Rate Master banega" decision me hai — **wahi authoritative hai, yeh entry sirf history ke liye rakhi hai.**

### ⚠️ SUPERSEDED (2026-09-25) — Part 2 backend order = dependency chain
**Date:** 2026-09-21 (superseded 2026-09-25)
**Kya tha:** Backend sequence: Unit → Work Stage → Machine → RM Category → Raw Material → Product Category → Product → **Vendor → Customer** (Warehouse sabse last).
**Kyun ulta hua:** User ne explicit maanga Warehouse ko Vendor se **pehle** banayein — spec khud Warehouse ko Phase-0-level foundation cheez maanta hai (stock/GRN/production sab isi pe depend karte hain), aur tracker.md already Warehouse ko "gap-fill, stock pages isपे depend karti hain" bol chuka tha. Naya order: ... → Product → **Warehouse (+ chhota Branch) → Vendor** → Customer. Poori Warehouse Master reasoning (fields, `warehouse_type` real-world gap, Branch approach) tracker.md ke 2026-09-25 Work Log entry me hai.
**How to apply:** Agla module Vendor Master hai. Customer Master ke baad bhi order dobara confirm kar lena — abhi tak assume hai ki wahi order (Vendor → Customer) rahega.

### Decision: Ledger `current_balance` user-editable nahi; opening edit = sirf delta
**Date:** 2026-09-25
**Kya:** Vendor/Customer ke ledger me `current_balance` **calculated** value hai (opening + transactions), form me uska input kabhi nahi hoga. Opening balance edit hone par `current_balance += (new_signed_opening - old_signed_opening)`. Signed convention: **Cr = plus, Dr = minus**; `current_balance` DB me signed store hota hai, display me `abs` + sign se Cr/Dr.
**Kyun:** User ne Vendor edit banate waqt poocha — dono editable hon to mismatch pakka. Current ko overwrite karne se beech ki purchases/payments ka hisaab ud jaata; opening badle aur current na badle to bhi galat. Delta approach dono problem solve karta hai. Dr↔Cr type badalne par bhi sahi chalta hai (2,000 Dr → 2,000 Cr = +4,000).
**How to apply:** Customer Master me same pattern. Phase 7 me har voucher bhi current ko isi signed tarike se +/- karega. FY close ke baad opening lock hoga (tab correction = adjustment entry). Money columns abhi `Float` hain — accounting shuru hone se pehle `Numeric(12, 2)` pe shift karna discuss karna.

### Decision: Warehouse = logical stock bucket, physical building nahi; Branch abhi lightweight
**Date:** 2026-09-25
**Kya:** (1) `Warehouse.warehouse_type` (RM/WIP/FG/SCRAP/QC_HOLD) enum rakha, lekin ismein ek warehouse-row ≠ ek physical jagah — chhoti company me 1-2 physical sheds ke andar bhi 5 alag "logical" warehouse-rows ban sakte hain (sabka `location` same/blank). Jitne types abhi chahiye utne hi banao (e.g. sirf RM+FG), baaki baad me add kar sakte ho — koi migration nahi chahiye, bas naya row. (2) `Branch` poora master nahi bana — chhota table (name, state, gstin) + Warehouse form ke andar inline "+Add branch" (rename/soft-remove "Manage" wala hissa skip kiya). Poora Branch/Company Master **Phase 0 (multi-tenancy)** me banega jab uski zaroorat aayegi.
**Kyun:** User ne khud sawaal uthaya — real business me shayad 1-2 hi physical warehouse hon, to fixed "1 type = 1 warehouse" assumption galat lagega. Resolution: "warehouse" software me sirf ek stock-tracking label hai, real jagah nahi — yeh QC_HOLD/Scrap jaisi automatic-routing logic (GRN → QC_HOLD → RM, production scrap → SCRAP) ke liye zaroori hai, isliye type hataya nahi, sirf uska matlab clarify kiya. Branch poora master banane se abhi over-engineering hoti (company single-location ho sakti hai), lekin `branch_id` FK schema me zaroori tha (spec ka DB hint) — isliye lightweight version.
**How to apply:** Jab bhi koi naya warehouse banaना ho — user ko yaad dilane ki zaroorat nahi ki "physical jagah = warehouse", bas jitne stock-buckets chahiye utne bana lo. Jab Phase 0 (Auth/Multi-Tenancy) aaye, tab poora Branch Master banega — abhi ke chhote `Branch` table/rows migrate/reuse ho sakte hain.

### Decision: Har module me teaching continue karo, sirf pehle module tak limited mat rakho
**Date:** 2026-09-16
**Kya:** Jaise-jaise similar modules (Vendor, Customer, Raw Material) bante gaye, explanation dheere-dheere sirf "kya badla pichle module se" tak simat gaya — asli teaching (kyun aisa design kiya, concept kya hai) kam hoti gayi. User ne yaad dilaya: "explain karo taaki main baad mein manual change kar paau, sikhate rehna, live project learning jaisa."
**Kyun:** User ka core goal shuru se hi yehi hai (development.md Section 0, memory.md ka teaching-style decision) — speed se zyada important hai ki user samjhe. Repetitive-lagne wale modules mein bhi naye concepts hote hain jo explain karne chahiye.
**How to apply:** Har naye module se pehle — agar usme koi genuinely NAYA concept hai (jaise Product Master ke dynamic attributes), usse code likhne se PEHLE plain language mein samjhao: naive approach kyun kaam nahi karega, alternative kya hai, screen pe kaisa dikhega. Sirf "yeh Vendor jaisa hi hai bas X badla" wala terse summary kaafi nahi hai.

---

### Decision: Unit soft-delete = alag flag `is_deleted` (Stopped se alag)
**Date:** 2026-09-19
**Kya:** Toggle Stop = `is_active=False` (Stopped filter me dikhe). Delete = `is_deleted=True` (DB me row rahe, lekin Unit Master list ke teeno filters — All / In use / Stopped — me na dikhe). Hard `db.session.delete` nahi.
**Kyun:** User ne clear kiya deleted rows frontend pe bilkul nahi; inactive/stopped alag concept hai.
**How to apply:** List query hamesha `is_deleted == False` pehle; phir status se `is_active` filter. Delete route sirf `is_deleted=True`.

### Decision: Work Stage master + Machine FK; master list Search/Filter JS OK
**Date:** 2026-09-21
**Kya:** (1) Naya **Work Stage** master (code, name, sort_order, soft status) — Machine pe baad me `work_stage_id` FK dropdown. Free-text work_center hataenge. (2) Chhote masters pe search/filter **client-side JS** OK (Flask `?q=` har click pe zaroori nahi).
**Kyun:** Routing stages se match; FK seekhna; typo/mismatch kam. User ne JS search prefer kiya (fast/easy).
**How to apply:** Mock UI `/work-stages` pehle → model/CRUD → Machine FK. Badi lists pe Flask pagination baad me.

### Decision: Tax Rate Master banega, Product ka tax field FK hoga (not hardcoded/unused)
**Date:** 2026-09-23
**Kya:** Dedicated **Tax Rate Master** (Code, Rate %, Label, Active/Stopped) bana — CRUD complete. Product model ka `tax_rate` (String) field replace hoke `tax_rate_id` (FK → `tax_rates.id`) banega.
**Kyun:** User Product Master pe HSN/tax_rate field samajhne me confuse hua ("GST me SGST/IGST alag hote hain, yeh field kis liye hai") — poora tax flow samjhaya (Product ka tax_rate = sirf SLAB %, CGST+SGST vs IGST split invoice pe customer/vendor state se decide hota hai, spec §1.2.2). Isi discussion me tay hua ki rate hardcode/unused chhodna galat hai — spec ka apna compliance disclaimer likhta hai *"make all thresholds/rates admin-configurable rather than hardcoded."* Isliye upar wala purana "abhi nahi" decision supersede hua.
**How to apply:** Naya module banao to hamesha dependency order follow karo (lookup/master pehle, phir usko FK se use karne wala module) — abhi jaisa Tax Rate Master, Product se pehle bana. Product Add/Edit form me ab Tax Rate dropdown Category/Unit jaisa hi FK-based hoga.

### Decision: Flask-Migrate use karo schema changes ke liye, baar-baar DB delete nahi
**Date:** 2026-09-23
**Kya:** Jab bhi koi SQLAlchemy model field add/remove/change ho (jaise Product ka `tax_rate` → `tax_rate_id`), ab se **Flask-Migrate** (Alembic wrapper) use karenge — `flask db migrate` + `flask db upgrade` — is existing data ko delete kiye bina schema update karega. Tech stack table (`CLAUDE.md` §2) me "DB Layer: SQLAlchemy" ke saath ab implicitly Flask-Migrate bhi shaamil hai.
**Kyun:** Pehle approach tha "`instance/erp.db` delete karo, `db.create_all()` fresh tables bana dega" — yeh kaam karta tha jab masters kam the, lekin ab (Unit/WorkStage/Machine/RmCategory/RawMaterial/ProductCategory/TaxRate — 7 masters test data ke saath) har schema change pe sab test data dobara type karna painful ho gaya. User ne explicitly poocha "baar baar db delete karna sahi option nahi he, koi aur option he" aur step-by-step sikhna chuna.
**How to apply:** Naya field/model badalne se pehle: model change karo → `flask db migrate -m "..."` (autogenerate diff) → migration script check karo → `flask db upgrade` (apply, data safe). `db.create_all()` (`app/__init__.py`) migrations setup ke baad hata diya jaayega — Migrate hi schema manage karega age se.

## Key Decisions

### Decision: Flask feature ke saath related HTML/Jinja bhi sikhao — chupke template mat badlo
**Date:** 2026-09-19
**Kya:** Part 2 me jab koi feature develop/seekhai ho (search, filter, form, toggle), AI sirf Python mat sikhayega / HTML khud silent edit nahi karega. Har aise step me CONCEPT + TYPE THIS me **Flask aur related HTML dono** — taaki user ko pata ho “backend change → template me yahan `name` / form / button / value”.
**Kyun:** User ne explicitly bola: AI HTML khud change kar deta hai aur batata nahi; kal ko khud maintain karne ke liye pair samajhna zaroori hai. Search step pe ye gap clear hua.
**How to apply:** Har micro-step jahan template touch ho: (1) CONCEPT me dono sides, (2) WHERE me dono paths, (3) TYPE THIS me chhota Python + chhota Jinja, (4) user type kare. Exception: user bole “tum likh do” / pure visual polish / Part 1 mockup-only.

### Decision: List Search/Filter pehle Flask (server) seekho; JS sirf chhote UI helpers
**Date:** 2026-09-19
**Kya:** Unit Master jaisi list pe Search / status filter pehle `request.args` + SQLAlchemy query se banengen. Client-side JS search optional polish baad me. Modal open/close jaisa chhota JS OK.
**Kyun:** User ko JS nahi aati; goal Flask se khud maintain karna hai. Server-side search ERP me badi data ke liye sahi bhi hai (pagination, security, bookmarkable URL).
**How to apply:** Naya list feature pehle route + form GET sikhao; “sirf JS se filter” tab jab user deliberately UI polish maange.

**Date:** 2026-09-17
**Kya:** Flask backend (Part 2) AI dump nahi karega. Har micro-step: CONCEPT → WHERE → TYPE THIS (chhota) → RUN → CHECK. User khud type karega. Poora playbook `learning.md`; Cursor rule `.cursor/rules/manual-learning.mdc`; `CLAUDE.md` §0A.
**Kyun:** User ka pehle se goal — AI/dost ke bina bhi maintain/debug. Claude session limit pe plan adhoora reh gaya tha; isliye rule files me permanently lock kiya taaki koi bhi agent continue kar sake.
**How to apply:** Part 2 start pe pehle `learning.md` + tracker Current Focus. Ek message = ek micro-step. Poori module files mat generate karo jab tak user explicitly na bole. Tracker me hamesha next micro-step ID likho (e.g. `Part2 / Unit / F5`).

### Decision: Naya phase shuru hote hi, sidebar section turant PEHLE hi file me add karo — baad ke liye mat chhodo
**Date:** 2026-09-17
**Kya:** Jab bhi koi naya phase/module-group (jaise Phase 3 Inventory, Phase 4 Manufacturing) shuru hota hai, uska sidebar nav-section (`<div>` heading + links) us phase ki **pehli hi file** me daal do — aur wahi block copy-paste karke us phase ki baaki saari files me bhi turant daalo, ek saath. "Baad me add karenge" mat socho.
**Kyun:** Phase 3/4 ki 8 Cursor-built files verify karte waqt do inconsistency bugs mile: (1) Phase 4 ki saari 4 files me "Procurement" sidebar section poora gayab tha (jabki Phase 3 files me tha) — matlab Manufacturing screen se seedha Procurement tak jaane ka koi rasta nahi tha. (2) Phase 3 ki 3 files me "Manufacturing" section bilkul nahi tha, 1 file me sirf aadha (1 link out of 4) tha — clearly alag-alag time pe alag-alag reference file dekh ke banayi gayi thi.
**Result:** Sabhi 8 files ka sidebar ab identical/consistent hai — Masters → Procurement → Inventory → Manufacturing, har section har file me poora.
**How to apply:** Future phases (Sales/E-Way Bill, Accounting, etc.) shuru karte waqt: (a) us phase ki pehli file banate hi uska sidebar-section-block save kar lo (reusable canonical version), (b) us block ko us phase ki HAR file me insert karo — pehli file banate waqt hi, last file tak wait mat karo, (c) verification pass me sabse pehle yeh check karo ki sab phases ke sidebar blocks har file me identical hain (ek file khol ke baaki se diff karna sabse tez tareeka hai).

---

### Decision: UI text hamesha English, sirf code comments Hinglish
**Date:** 2026-09-16
**Kya:** App ke andar jo bhi text end-user ko dikhta hai (buttons, tooltips, empty-state messages, alert() popups, help text) — hamesha **English** me hoga. Hinglish sirf code comments tak limited hai (`<!-- -->`, `//`, `/* */`, Python `#`).
**Kyun:** Vendor Master ke View panel me maine galti se Payment Terms/Opening Balance ke explanation notes Hinglish me likh diye the seedha UI ke andar (jaise "30 din ka credit period"). User ne turant point out kiya "web me aisa Hinglish text nahi chahiye" — matlab yeh ek real product hai, professional English UI honi chahiye; Hinglish sirf development-time ka tool hai (mujhe/user ko code samajhne ke liye), end-user-facing nahi.
**Result:** Unit, Machine, Vendor teeno mockups me poora sweep kiya — saare visible strings English me convert kiye (comments waise hi Hinglish rahe).
**How to apply:** Naya module banate waqt shuru se hi yeh yaad rakho — jo bhi `<span>`, `<p>`, button text, `title=""`, `placeholder=""`, `alert()`, JS string jo screen pe dikhega — English likho. Sirf `<!--` comment ya `//`/`/* */` ke andar Hinglish likhna hai.

---

### Decision: Transaction documents me status-advance buttons live hone chahiye, sirf decorative nahi
**Date:** 2026-09-16
**Kya:** Jab kisi document ka koi "next step" button ho (PO ka "Confirm", GRN ka "Post GRN", Invoice/Return ka "Post"), usse sirf button ki tarah dikhana kaafi nahi — click karne par row ka status/badge/related fields turant (client-side, mock) update hone chahiye, jaisa Phase 1 ke toggle-switch me hota tha. Isi tarah jo "byproduct" documents automatically generate hote hain (jaise QC reject hone par "Rejection Memo") unka bhi apna **View panel** hona chahiye, sirf naam mention karna kaafi nahi.
**Kyun:** User ne dekha ki Cursor-built Phase 2 mockups me "Memo" button aur "Confirm"/"Post GRN"/"Post" buttons sirf dikhave ke the — click karne par kuch hota hi nahi tha. Isse flow "samajhne" ka poora maksad adhoora reh jaata — user poochh baitha "memo kahan se dekhein, status kaise badlenge."
**Result:** `inward_qc.html` me Memo view panel banaya; `purchase_order.html`/`gate_inward_grn.html`/`purchase_invoice.html`/`purchase_return.html` me status-advance buttons ko live kiya (row update + filter count update + mock alert).
**How to apply:** Future transaction-flow modules (Phase 3 onwards) me shuru se hi yeh pattern follow karo — koi bhi "Draft→next status" button banao to usse turant hi wire kar do, baad me alag se fix karne ka wait mat karo. Byproduct/auto-generated documents (memos, vouchers, etc.) ka bhi apna mini View panel banao unke pehli baar mention hote hi.

---

### Decision: "View" button pattern — jab table me kuch fields hide hon, unhe read-only panel me dikhao
**Date:** 2026-09-16
**Kya:** Jab kisi module ki table me saari fields nahi dikhti (jaise Vendor Master — 15 fields hain, table me sirf 9), tab Actions column me "Edit" ke saath ek **"View" button** bhi hona chahiye jo saari fields (jo table me nahi hain wo bhi) ek **read-only** slide-over panel me dikhaye — Edit se alag color (neutral, copper nahi) taaki galti se edit-mode na khule.
**Kyun:** User ne Vendor Master ki table dekh ke kaha "Payment Terms/Opening Balance samajh nahi aaya, mujhe sari fields samjhao aur data dekhne ke liye View button chahiye" — matlab sirf explain karna kaafi nahi tha, UI me hi ek permanent "dekhne ka tareeka" chahiye tha jo baar-baar poochne ki zaroorat na banaye.
**Result:** Vendor Master me View button + panel add kiya, saath hi confusing fields (Payment Terms, Opening Balance) ke column headers pe hover-tooltip bhi add kiya, aur View panel ke andar in fields ke aage chhota plain-language explanation bhi ("Net 30 = 30 din ka credit period", "₹15,000 Cr = hum vendor ko dena baaki hain").
**How to apply:** Customer Master (jo Vendor jaisa hi 11+ field wala module hai) me bhi yehi View pattern chahiye. Unit/Machine Master ko View button ki zaroorat nahi thi kyunki unki saari fields already table me dikh rahi thi — sirf tab View add karo jab table curated/incomplete ho.

---

### Decision: Field-completeness decisions Claude khud le, user sirf visual/UX review kare
**Date:** 2026-09-16
**Kya:** Jab bhi kisi module ke fields decide karne hon (kaunse fields honge, kya zaroori hai), Claude requirements doc (`Manufacturing_ERP_Unified_Requirements_Specification.md` Section 4) se seedha nikal ke decide karega — user se field-by-field confirmation nahi maangega. User ka review sirf **visual/UX** cheezon tak limited hai (layout, colors, spacing, kya use karne mein aasan hai) — fields ka business-correctness woh judge nahi kar sakta.
**Kyun:** User ne khud kaha "mujhe nahi pata inme kya fields aayenge, tu soch ke batana" — unke paas ERP/accounting domain knowledge nahi hai (ki Vendor Master me GSTIN/PAN/Payment Terms kyun zaroori hain), isliye unse field-list approve karwana unfair hai — wo meaningfully evaluate nahi kar sakte.
**How to apply:** Naya module banate waqt fields seedha requirements doc se lo (jo already research kiya hua hai), zaroorat ho to reasonable business judgment se thoda extend karo (jaise Bank Details ko Bank Name/IFSC/Account Number me todna), aur user ko sirf yeh poocho "yeh page dikhta/use hota kaisa hai" — "yeh fields sahi hain kya" mat poocho.

---

### Decision: Workflow revise — "sab mockups pehle, phir sab backend" (Part 1 / Part 2 split)
**Date:** 2026-09-16
**Kya:** Purana plan tha: har module (Unit, Machine, Vendor, Customer, Raw Material, Product) ka poora A→B→C→D loop ek-ek karke poora karo, tabhi agle module pe jao. **Yeh badal diya gaya hai.** Naya plan: pehle sab 6 modules ke sirf Step A (mock frontend) banao aur approve karo (**Part 1**), sab mockups dekhne ke baad hi kisi bhi module ka backend (Step B/C/D) shuru hoga (**Part 2**).
**Kyun:** User ne explicitly kaha "taaki hum jaan sakein ki kaise sab kahan join hota hai" — matlab poori ERP ka visual/structural picture pehle dekhna chahte hain (sab sidebar links, sab pages ka look) taaki system ka overall shape samajh aaye, uske baad hi technical/backend complexity me jaayein.
**Important context:** Yeh decision **kal ke decision (2026-09-15) se ulta hai** — kal explicitly poocha gaya tha (2 options: "continue per-module" vs "sab mockup pehle") aur user ne "continue per-module" chuna tha. Aaj mann badal gaya. Isliye Unit Master ka backend (jo pehle se ban chuka tha aur tested tha — Flask app, SQLite database, Add/Toggle routes) **jaan-boojhkar delete kar diya gaya** taaki sab 6 modules exactly same stage (sirf mockup) pe ho, koi ek module aage na ho.
**Result:** `development.md` Section 0 revise kiya (Part 1/Part 2 structure), `tracker.md` ka Phase 1 tracker bhi isi structure me restructure kiya. `app/`, `run.py`, `requirements.txt`, `instance/erp.db` delete kiye — dobara Part 2 me banenge (isi baar bhi bilkul same tareeke se, kyunki wo approach kaam kar rahi thi, sirf timing badli hai).
**How to apply:** Agar user phir se mann badle, is baar bhi CLAUDE.md ke rule ke hisaab se — pehle purane decision se conflict point out karo, confirm karo, phir badlo. Backend dobara banate waqt Unit Master ke liye maine jo code likha tha wahi pattern use karna (models.py/extensions.py/routes.py structure) — dobara design karne ki zaroorat nahi, bas dobara likhna hai.

---

### Decision: Jinja templates me hamesha `{# #}` comment use karo, `<!-- -->` nahi
**Date:** 2026-09-15
**Kya:** Flask/Jinja `.html` template files (base.html, units.html, aage sab modules) me comments likhte waqt hamesha Jinja ka apna `{# ... #}` style use karna — normal HTML `<!-- ... -->` comment nahi. Aur `{# #}` comment ke ANDAR bhi kabhi ek aur nested `{# #}` ya literal curly-percent/curly-curly example likhne ki koshish mat karna — jaise hi ek premature closing sequence milti hai, comment wahin khatam ho jaata hai aur baaki text real template code ki tarah parse hone lagta hai (syntax error deta hai).
**Kyun:** Step B (Unit Master Flask conversion) banate waqt yeh exact galti hui — `base.html` ke top comment me HTML-style comment ke andar Jinja tag syntax example likha tha, jo khud Jinja engine ne parse karne ki koshish ki aur `TemplateSyntaxError` diya. Server test karte waqt (curl se `/units` hit kiya) yeh pakड़ा gaya.
**How to apply:** Naya template file banate waqt (Machine, Vendor, Customer, etc.) top-level ya inline comments ke liye `{# ... #}` use karo, aur comment ke andar Jinja syntax "example" dena ho to literal `{%`/`%}`/`{{`/`}}`/`{#`/`#}` characters likhne se bacho — words me describe karo (jaise "curly-percent tag" ki jagah seedha likh dena).

---

### Decision: Table columns — fixed px width for content, ek column flexible (px-based colgroup technique)
**Date:** 2026-09-15
**Kya:** Data tables me `%`-based colgroup widths use nahi karni — bade/wide screen par short-text columns (jaise "Full name": "Kilogram", "Gram") % width ke hisaab se zabardasti stretch ho jaate hain aur beech me bada khaali gap dikhta hai. Sahi tarika: `table-layout: fixed` rakho, per-column **fixed px width** do (content ke hisaab se, jaise # =44px, Code=92px), aur flexible column (usually "Actions", jahan trailing space normal dikhta hai) ko **explicit `width: calc(100% - <baaki columns ka total px>)`** do.
**Correction 1 (same day):** Pehle socha tha ki flexible column ka `<col>` bas width-less chhod dene se (koi width attribute hi nahi) wo khud bachi hui jagah le lega — practically yeh reliably kaam nahi kiya (Actions column chhota reh gaya, page ka right side pura blank dikha). `calc(100% - Npx)` explicit value dene se yeh guaranteed kaam karta hai.
**Correction 2 / Final decision (same day):** `calc()` se Actions column ko poora leftover space diya to Actions hi bahut chauda (30%+) ho gaya aur wahi "ek jagah bada khaali block" problem repeat ho gayi, bas column badal gaya. User ko 2 options diye (AskUserQuestion se): (a) table ko compact/content-width rakho, ya (b) poori width cover karo lekin gap har column me evenly spread karo. **User ne (b) chuna.** Final approach: colgroup % based hai (#5%, Code9%, Full name22%, Base unit14%, Status20%, Actions30%), aur **saare columns (headers + data cells) center-aligned** hain (`text-align:center` — sirf # column left rehta hai) + Actions ke andar Edit/Toggle bhi `justify-center` se center kiye. Isse extra space kisi ek jagah "khaali block" nahi lagta, balki har cell me evenly padding jaisa spread hota hai.
**How to apply (updated):** Future modules me bhi is "poori width + center-align sab kuch" pattern ko default maano jab tak user kuch aur na kahe — sirf ek column ko flex/calc dena (jaisa pehle try kiya) is user ke liye kaam nahi karta.
**Kyun:** Pehle attempt me maine page/`<main>` ka hi max-width chhota kar diya tha (1680→1120px) taaki columns ke gaps chhote dikhein — lekin isse page ke SIDE me khaali jagah dikhne lagi, jo user ko bilkul pasand nahi aaya ("pehle sahi tha"). Asli problem page-level nahi, table-level tha — column sizing ka tareeka galat tha.
**Result:** `<main>` ka max-width cap poora hata diya (page phir se full-width hai). Table ke colgroup ko %  se px me convert kiya, sirf Actions column flexible chhoda. `mockups/unit_master.html`.
**How to apply:** Future modules (Machine, Vendor, Customer, Raw Material, Product tables) me bhi yehi pattern follow karo — pehle content dekh ke har column ka natural px width tay karo, phir sirf ek "safe" trailing column (aksar Actions) ko flexible rakho. Kabhi bhi poori page ko chhota mat karo sirf table ke andar ke gaps fix karne ke liye — yeh do alag problems hain.

---

### Decision: Status badges (green/red) brand-theme-lock se alag hain
**Date:** 2026-09-15
**Kya:** Sidebar/buttons/header/links etc. (brand chrome) sirf Ink/Copper/Teal/Mist use karenge — lekin Active/Stopped jaise status badges ke liye `success` (green) aur `stop` (red) naam se do alag tokens `tailwind.config` me defined hain. Yeh brand-lock rule violate nahi karte.
**Kyun:** Requirements doc (Section 6.3) khud semantic status colors (green=success/active, red=error/stopped) mandate karta hai — ERP me status turant pehchanna zaroori hai, sirf copper/teal se "active vs stopped" clearly distinguish nahi hota. User ne "header me green sahi nahi laga" complain kiya tha — asli issue yeh tha ki "Quick help" link ka stray teal color toolbar me akela odd lag raha tha, aur status badges inline `style="..."` (CSS variables) se ban rahe the jo Tailwind class system se inconsistent tha — status concept khud galat nahi tha.
**Result:** `success`/`stop` tokens add kiye, saare status badges/buttons ab consistent Tailwind classes use karte hain (koi inline style nahi). "Quick help" link color copper-text kar diya. Saath hi Cursor ne "Category" aur "Used in" naam ke 2 faltu columns add kar diye the (requirements doc ke Unit table schema me hain hi nahi) — hata diye.
**How to apply:** Future modules me bhi status/success/error indicate karne ke liye green/amber/red use karna theme-lock rule todna nahi maana jayega — lekin brand chrome (nav, buttons, headers) hamesha Ink/Copper/Teal/Mist hi rahega.

---

### Decision: Brand color plate + logo (Wire Soldering ERP)
**Date:** 2026-09-15
**Kya:** Default sky-blue/slate theme hata ke business-fit palette:
- **Ink** `#0F2F32` — sidebar / dark surfaces
- **Copper** `#C46B2D` — primary buttons, active nav, accents (copper wire feel)
- **Teal** `#2A6B6E` — info/tips
- **Mist** `#F3F5F4` — page background
Logo file: `mockups/assets/wire_soldering_logo.png` (coil/W mark, ink + copper).
**Kyun:** User ko generic blue theme pasand nahi aaya; wire soldering business ke liye copper + factory ink zyada relevant aur recognizable hai.
**Update (same day):** Dark sidebar pe logo white-box / chhota dikh raha tha — sidebar **light white** kar diya, logo 48px + `object-contain`, design swatches user UI se hata diye. Active menu = soft copper bg + border.
**Rule:** UI me **gradient colors mat use karo** — sirf solid brand colors (Ink / Copper / Teal / Mist).
**Rule (user feedback):** Color theme bar-bar mat badlo. Light sidebar + copper accents **locked**. UI/UX improve karte waqt sirf spacing/layout/density/clarity touch karo — theme mat flip karo.
**How to apply:** Future mockups/Flask templates isi CSS variables / Tailwind `ink`/`copper`/`brand` colors follow karein — naya random blue/purple/dark theme mat lao. Gradients bhi mat lao.

### Decision: Do purani requirement docs ko ek unified doc me merge kiya
**Date:** 2026-09-15
**Kya:** `Dynamic_Manufacturing_ERP_Master_Requirements_Specification.md` (English, compliance-heavy) aur `manufacturing_erp_module_wise_phase_flow_requirements-1.md` (Hinglish, functional flow) — dono ko merge karke `Manufacturing_ERP_Unified_Requirements_Specification.md` banaya.
**Kyun:** Dono docs same "Phase N" number pe alag-alag content rakhte the (jaise Phase 6 ek doc me Sales/E-Invoicing tha, doosre me Lab/QC) — isse confusion hoti. Doosri doc me E-Invoicing/E-Way Bill ko "future/optional" bataya gaya tha jabki ₹15Cr+ turnover pe yeh legally mandatory hai.
**Result:** Ab sirf ek hi Phase roadmap (0–13) use hoga — purani do files sirf reference/backup ke liye Downloads folder me move kar di gayi hain, unko future development ke liye use nahi karna.

---

### Decision: Tech Stack — Flask + Jinja2 + Tailwind CSS (CDN) + SQLite + SQLAlchemy
**Date:** 2026-09-15
**Kya:** Poore project ke liye React/Laravel/separate JS framework use nahi karenge. Sab kuch Flask (Python) centric rahega.
**Kyun:**
- User (business owner) ne khud bataya: unko Flask thoda-bahut aata hai, React/Laravel/HTML-CSS-JS nahi aata.
- Main concern yeh thi: agar future me koi AI coding agent available na ho, toh user khud errors solve kar sake — isliye single-language (Python), well-documented, huge-community stack chuna.
- Laravel option tha (dost jaanta hai) lekin reject kiya kyunki isse user apne dost pe hi permanently dependent ho jaata — jo exactly wo problem hai jisse bachna hai.
- Database: PostgreSQL ki jagah **SQLite** se shuru kiya — kyunki SQLite ek single file hai, koi separate database server manage nahi karna padta (ek kam moving part = kam cheezein jo galat ho sakti hain). Business jab multi-user scale pe jayegi, tab SQLAlchemy ke through PostgreSQL pe migrate kar sakte hain.
- Tailwind CSS rakha (sirf CSS classes, koi build step/install nahi — CDN link se) lekin shadcn/ui (jo React-only hai) drop kiya.
**Result:** `development.md` isi stack ke around likha gaya hai. Koi bhi future kaam isse deviate na kare bina explicit discussion ke — yeh rule `CLAUDE.md` me bhi likha hai.

---

### Decision: Development Workflow — Mock Frontend First, Har Module Alag-Alag
**Date:** 2026-09-15
**Kya:** Har module (Unit, Machine, Vendor, Customer, Raw Material, Product) 4 steps se guzarta hai: A) static HTML mockup (fake data) → B) Flask/Jinja2 me convert → C) database + backend → D) real data se connect. Ek time pe ek hi module, sab saath me nahi.
**Kyun:** User ne explicitly kaha ki pehle mock frontend dekh ke approve karna chahte hain, tabhi aage badhna hai — taaki backend rebuild na karna pade agar UI me kuch missing nikle. Chhote steps isliye taaki user seekh bhi sake aur har cheez samajh ke aage badhe.
**Result:** Poora plan `development.md` me hai. `tracker.md` me har module ke 4 steps checkbox se track hote hain.

---

### Decision: Mock Frontend (Step A) ab Claude khud banata hai (Cursor nahi)
**Date:** 2026-09-15 (original), **Revised 2026-09-16**
**Kya (original):** Step A ke static HTML mockups user khud **Cursor** (AI code editor) se banwayenge, Claude sirf review/check karega.
**Kya (revised 2026-09-16):** User ne kaha "hum Cursor se nahi banva rahe, tum khud banao" — ab Claude directly mockup HTML files banata hai, Unit Master (`mockups/unit_master.html`) ke approved theme/design/UI-UX ko exactly follow karte hue (Ink/Copper/Teal/Mist colors, IBM Plex Sans font, full-width center-aligned tables, sidebar pattern, toggle-switch ya status-badge pattern).
**Kyun:** Cursor se banwane me kaafi rounds lage the (green header, faltu columns, font size, spacing issues) jo baar-baar Claude ko hi fix karne pade — user ne decide kiya seedha Claude khud banaye, established design system follow karte hue, taaki pehli baar me hi sahi aaye.
**How to apply:** Naya module mockup banate waqt hamesha `mockups/unit_master.html` ko reference/base banao — wahi color tokens, font, table column-sizing technique (fixed % + center-align, jaisa memory.md ke "Table columns" decision me hai), sidebar structure copy karo, sirf us module ke apne fields/data badlo.

---

### Decision: Code Comments Hinglish me, Beginner-Friendly
**Date:** 2026-09-15
**Kya:** Har Python/HTML file me comments Hinglish (mix Hindi-English, Roman script) me likhe jayenge, jo batayein "yeh kya kar raha hai" aur "kyun zaroori hai" — taaki user khud manually code padh ke samajh sake aur edit kar sake.
**Kyun:** User professional developer nahi hai, seekhte hue project banwa raha hai, aur future me AI agent ke bina bhi khud maintain karna chahta hai.
**How to apply:** Sirf English technical comments kaafi nahi — jahan bhi non-obvious logic ho (jaise "kyun soft-delete kar rahe hain, hard-delete nahi"), Hinglish me ek line explain karo.

---

## Session Log

*(Chhote updates jo Key Decisions jitne bade nahi hain, lekin future context ke liye useful hain. Naya entry sabse upar.)*

### 2026-10-01
- Product recipe UI + save aage badha. RM flags (`is_base_metal` / `is_core_flux`) mutually exclusive buttons. Migration `631aec3a18e5` ko `server_default=sa.false()` chahiye tha (SQLite NOT NULL without default fail).
- `products_add` = Product + default variant + recipe lines. `products_variants_edit` user ne type kiya: attributes update + recipe replace. Variant modal pe product jaisa flow preview (order qty / weight / material qty).
- Abhi baaki: `products_variants_add` recipe save, phir `products_edit` (default variant attributes + recipe). Product add ka soft-deleted restore abhi variant/recipe nahi banata.

### 2026-09-17
- **Inline list Add + Manage:** Raw Material / Product Category aur Warehouse Branch pe form me hi `+ Add` + `Manage` (rename / soft-remove). Shared helper: `mockups/assets/erp-list-picker.js`. Hard-delete nahi.
- **Warehouse Master gap-fill:** Stock/transfer/issue screens warehouse names use kar rahe the lekin master nahi tha. Spec §4.1 pehle se require karta hai. Mock: `mockups/warehouse_master.html` (type RM/WIP/FG/SCRAP/QC_HOLD + branch + location + active). Sab sidebars me Masters → Warehouses link.

### 2026-09-15
- User ne apna background clarify kiya: sirf thoda Flask aata hai, React/Laravel/JS nahi aata, dost Laravel jaanta hai but usse permanently dependent nahi hona chahta. Yeh context tracker/memory/CLAUDE.md teeno me capture kiya gaya hai.
- `development.md`, `tracker.md`, `memory.md`, `CLAUDE.md` — yeh 4 project-management files banayi taaki multi-session project ka context kabhi na khoye.
