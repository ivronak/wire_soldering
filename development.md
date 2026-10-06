# Phase 1 — Step-by-Step Development Plan
### Master Data Management & Dynamic Attributes

---

## 0. How We Will Work (Read This First)

This is not a normal "write all the code at once" plan. We are going to work in **small, visual steps** so that you can see and approve each piece before we move forward, and so you can learn the codebase as it grows instead of receiving a giant pile of code at the end.

### The Golden Rule of This Project (Revised 2026-09-17): Mockups First, Then Backend — But Backend Is **Taught + User-Typed**

Every module still goes through Step A → B → C → D. Part 1 (all mockups) first.  
**Part 2 change (MOST IMPORTANT):** AI does **not** dump backend code. User **types** Flask themselves; AI teaches one micro-step at a time. See **`learning.md`**.

```
PART 1 — MOCKUPS (mostly done)
  STEP A: static HTML mockups…

PART 2 — BACKEND (Manual Learning Mode ⭐)
  Foundation micro-steps F1, F2… (venv, run.py, app factory)
  Then per module, one at a time:
  STEP B / C / D broken into micro-steps (user types, AI guides)
  Tracker Current Focus = exact next micro-step ID
```

**Why Part 2 is manual:** so you can maintain/debug without an AI agent later. Speed comes from repeating the same pattern (Unit → Machine → …), not from AI writing everything.

### Tech Stack (confirmed)

| Layer | Choice | Why |
|---|---|---|
| Backend | **Flask** (Python) | You already know it a little; one language for almost everything |
| Templates | **Jinja2** (built into Flask) | No separate frontend framework to learn |
| Styling | **Tailwind CSS** (via CDN link, no build step) | Just CSS classes in HTML, nothing to install/compile |
| Database | **SQLite** (a single `.db` file) | Zero setup, no server to run/manage; we can migrate to PostgreSQL later once the business needs multiple concurrent users |
| DB Access | **SQLAlchemy** (Python library) | Lets you write Python instead of raw SQL for most things |
| JavaScript | **Vanilla JS, minimal** | Only for things like search/filter/modal toggling — no React, no build tools |

### Learning Habit for This Project

Code comments explain both **what** a piece of code does and **why** it's there (non-obvious decisions especially) — in Hinglish, so you can read the file later without me and still follow it. Keep a habit of actually reading these — that's how the "I can fix it myself" goal actually happens.

**Part 2 (2026-09-17):** You type the backend; the agent only teaches. Full rhythm in `learning.md` (CONCEPT → TYPE THIS → RUN → CHECK). Do not skip typing "to go faster" — the practice *is* the speed for later modules.

---

## 1. Project Folder Structure (what we're building toward)

```
wire_soldering/
│
├── mockups/                     ← PART 1 files live here (static HTML, fake data, no Flask needed)
│   ├── unit_master.html
│   ├── machine_master.html
│   ├── vendor_master.html
│   ├── customer_master.html
│   ├── raw_material_master.html
│   ├── product_master.html
│   ├── warehouse_master.html
│   └── assets/
│       └── wire_soldering_logo.png
│
├── app/                          ← the real Flask application (PART 2 onwards)
│   ├── __init__.py               ← creates the Flask app, connects the database
│   ├── models.py                 ← database table definitions (SQLAlchemy)
│   ├── extensions.py             ← database connection setup
│   │
│   ├── units/                    ← one folder per module
│   │   ├── routes.py             ← URLs + logic for Unit Master
│   │   └── templates/
│   │       └── units.html
│   ├── machines/
│   ├── vendors/
│   ├── customers/
│   ├── raw_materials/
│   ├── products/
│   │
│   ├── templates/
│   │   └── base.html             ← shared layout (sidebar) every page extends
│   │
│   └── static/
│       └── img/                  ← logo etc.
│
├── instance/
│   └── erp.db                    ← the actual SQLite database file (auto-created)
│
├── requirements.txt              ← list of Python packages needed
├── run.py                        ← the file you run to start the server
└── development.md                ← this file
```

We will create the `app/` folder (and everything inside it) only when **Part 2 (Backend)** starts — for now, during Part 1, only the `mockups/` folder exists and grows one file at a time.

---

## 2. Module Build Order

### Part 1 (Mockups) — original learning order (unchanged)
Mockups is order me ban/approve hue: Unit → Machine → Vendor → Customer → Raw Material → Product (+ later Warehouse / category mocks).

### Part 2 (Backend) — dependency order (locked 2026-09-21)

User ne decide: parties (Vendor) se pehle materials/products + unki categories, taaki FK dropdown real data se aaye.

| # | Module | Status / why |
|---|---|---|
| 1 | **Unit Master** | Done — base for RM / Product units |
| 2 | **Work Stage** | Done — Machine FK |
| 3 | **Machine Master** | Done — Work Stage FK |
| 4 | **RM Category** | **Next** — Raw Material category dropdown |
| 5 | **Raw Material** | Unit FK + RM Category FK |
| 6 | **Product Category** | Product category dropdown |
| 7 | **Product Master** | Category FK; variants later |
| 8 | **Vendor Master** | Rich form + Auto-Ledger; after materials exist |
| 9 | **Customer Master** | Vendor pattern + Debtors |
| 10 | **Warehouse** | Stock / inventory pages |

*(Old Part 2 table put Vendor right after Machine — superseded by this dependency order.)*

---

## 3. Part 1 — Mockup Plan, Module by Module

### Shared review checklist (applies to every module's Step A, every time)

- [ ] Every field listed below (from the requirements doc) is present — nothing missing.
- [ ] No invented/extra fields that aren't in the requirements doc (keeps the mock honest about what the real schema will be).
- [ ] Same visual theme as `unit_master.html` — Ink/Copper/Teal/Mist colors, IBM Plex Sans font, full-width table with the fixed-%-width + center-align column technique, sidebar with correct page highlighted.
- [ ] Status/enum fields use the right control: a toggle switch for a true 2-state field, a status badge + dropdown for 3+ states (like Machine Master's 4-state status).
- [ ] Search box + filter pills work (live JS filtering, no page reload).
- [ ] JS functions have short "what this does" comments, not just "why" comments.
- [ ] Sidebar link to/from other already-built mockups works (real `href`, not `#`).
- [ ] **You say "haan yeh sahi hai" before we move to the next module.**

---

### Module 1: Unit Master — ✅ APPROVED (2026-09-15)

**File:** `mockups/unit_master.html`
**Fields used** (spec Section 4.5): Code, Name, Is Base Unit, Active/Inactive.
**Design notes:** the "template" mockup — established the whole visual system (colors, font, table technique, toggle-switch pattern for simple 2-state status) that every other module now copies from.
**Known gap (not blocking):** the spec's Unit Conversion Engine (e.g. "1 KG = 1000 Gram", material-specific conversions) isn't in this mockup — it's a separate small feature we can add as a stretch item later if needed, doesn't block Phase 1.

---

### Module 2: Machine Master — ✅ APPROVED (2026-09-16)

**File:** `mockups/machine_master.html`
**Fields used** (spec Section 4.7): Machine Code, Name, Work Center, Capacity/Rated Output, Installed Date, Status (`Active` / `Under Maintenance` / `Breakdown` / `Retired`).
**Intentionally not a table column:** "Linked Maintenance Schedule" — the spec describes this as a capability this master *feeds into*, not a field to capture here; treating it as a separate future feature keeps this master simple.
**Design notes:** 4-value status meant a dropdown + colored badge instead of Unit Master's toggle switch — added two new status color tokens (`warning` amber for Maintenance, `neutral` gray for Retired). Only "Retired" dims the row (Maintenance/Breakdown stay full-opacity since they need attention, not hiding).

---

### Module 3: Vendor Master — ✅ APPROVED (2026-09-16)

**File:** `mockups/vendor_master.html`
**Fields** (spec Section 4.3): Code, Name, Contact Person, Mobile, Email, Address, GSTIN, PAN, State, Payment Terms, Opening Balance, Bank Details, Documents, Vendor Type, Active/Inactive.

**Design notes (this module changes shape, not just fields):**
- 15 fields is too many for Unit/Machine's small slide-over panel — the "Add/Edit Vendor" form needs to be **sectioned**: Basic Info (Code, Name, Contact, Mobile, Email, Address, State) → Tax & Compliance (GSTIN, PAN) → Payment & Bank (Payment Terms, Opening Balance, Bank Details) → Documents (Vendor Type, file-attach placeholder).
- The **table view** should show a curated subset, not all 15 columns — e.g. Code, Name, Contact, State, GSTIN, Payment Terms, Opening Balance, Status, Actions. Full detail lives in the Edit form, not the grid (this matches Section 20.5's data-grid density rules — don't cram everything into the row).
- "Documents" → just a visual placeholder (an "Attach file" drop-zone), no real upload logic — actual file handling is Section 16 (Documents module), a later phase.
- "Vendor Type" → a dropdown, admin-extensible in spirit (e.g. Raw Material Supplier, Job Worker, Transporter) — fake options in the mock, but must not look hardcoded/fixed-forever.
- A small note near the Save button: *"Saving this Vendor will auto-create a ledger under Sundry Creditors"* — just a UI hint for now; the real auto-ledger logic is backend (Part 2 / later accounting phase), per spec Section 4.3.

---

### Module 4: Customer Master — ✅ APPROVED (2026-09-16)

**File:** `mockups/customer_master.html`
**Fields** (spec Section 4.3): Code, Name, Contact, GSTIN, PAN, Address, Payment Terms, **Credit Limit**, Opening Balance, Bank Details, Documents, Active/Inactive.
**Design notes:** reuse Vendor Master's sectioned-form pattern almost exactly — swap out "Vendor Type" for **Credit Limit** (a numeric field, tabular-nums, probably with a currency ₹ prefix), auto-ledger note becomes *"...under Sundry Debtors"* instead of Sundry Creditors. Should be the fastest module to build since the pattern is already proven.

---

### Module 5: Raw Material Master — ✅ APPROVED (2026-09-16)

**File:** `mockups/raw_material_master.html`
**Fields** (spec Section 4.4): Code, Name, Category, Description, **Base Unit**, Alternate Units, Conversion, Reorder Level, Min Stock, Max Stock, HSN, Valuation Method, Active/Inactive.
**Design notes:**
- **First real cross-module relationship:** "Base Unit" must be a dropdown populated from Unit Master's data (KG, GM, PCS, MTR, LTR, BOX, TON — same fake list as `unit_master.html`, kept in sync manually for now since there's no real database yet). This is the mock's way of proving the "no hardcoded dropdowns" rule visually before the backend enforces it for real.
- "Category" is also a dropdown, admin-extensible in spirit (not a fixed enum) — same treatment as Vendor Type.
- "Valuation Method" → dropdown: FIFO / Weighted Average (per spec Section 6.4).
- Reorder Level / Min Stock / Max Stock are numeric — tabular-nums, right-aligned or centered consistent with the rest of the table.
- Per spec Section 4.4: **"Master price is never fixed"** — there is deliberately no "Rate" or "Price" field anywhere on this master; rate is only ever entered at purchase transaction time (a later phase). Don't add one even if it feels incomplete without it — that's correct per the spec.

---

### Module 6: Product Master + Dynamic Variants — ✅ APPROVED (2026-09-16)

**File:** `mockups/product_master.html`
**Fields** (spec Section 4.6): Code, Name, Category, Description, Base Unit, HSN, Tax, Active/Inactive — **plus** dynamic attributes (Size, Thickness/MM, Length, Gauge, Color, Grade — configurable, not fixed columns) — **plus** Variants, each with a unique SKU (e.g. `WSH-SM-2MM`).
**Design notes:**
- Two-level data: a **Product** (parent, e.g. "Wire Soldering") has multiple **Variants** (e.g. Small/2MM, Medium/3MM, Large/5MM), each a real sellable/stockable item with its own SKU. The mock needs to show both levels clearly — e.g. a Product list where each row expands (or links) to its Variant list.
- Dynamic attributes UI: since attributes are meant to be admin-configurable (not fixed schema columns per the spec's "no hardcoded attributes" rule), the Add/Edit Variant form should show an **"Add attribute" pattern** (a repeatable key+value row — "Size: Small", "Thickness: 2MM" — with a way to add more rows), not fixed input boxes labeled Size/Thickness/Length/Gauge/Color/Grade.
- Nice-to-have: a live SKU preview that assembles from the attribute values as you type (matching the spec's own example `WSH-SM-2MM`), though this can be a simple JS string-concatenation in the mock, not real logic.
- This is intentionally the last mockup — by now the design system, form patterns, and dropdown-from-another-master pattern (from Raw Material Master) will already be familiar, making this harder module easier to tackle.

---

### Module 7 (gap-fill): Warehouse Master — ✅ APPROVED (2026-09-17, verified)

**File:** `mockups/warehouse_master.html`
**Why added late:** Phase 3 stock screens pe warehouse names use ho rahe the, lekin master list nahi thi — user ne point kiya. Spec §4.1 me pehle se required tha. Root cause: har transaction screen apna hi hardcoded warehouse dropdown use kar raha tha — direct "no hardcoded dropdowns" rule (Section 5) violation. Warehouse Master ab single source of truth hai.
**Fields** (spec Section 4.1 + schema `branch_id`): Code, Name, Type enum (`RM` / `WIP` / `FG` / `SCRAP` / `QC_HOLD` — real schema enum, fixed list rakhna sahi hai, yeh hardcoded-dropdown violation nahi), Branch, Location, Active/Inactive (soft-stop only).
**Design notes:**
- Fake rows stock/manufacturing screens se match: Main RM Warehouse, FG Warehouse, Scrap Warehouse, QC Hold Bay, WIP Staging (+ one Stopped branch store).
- Type badges color-coded; filter by Active/Stopped + type dropdown.
- Branch inline add/manage picker — naya shared helper `assets/erp-list-picker.js` (generic, reusable for future Category-jaisi dropdowns bhi), full alag Branch Master page nahi banaya (abhi zaroorat nahi, sirf naam + optional State/GSTIN chahiye).
- Sidebar: Masters me Products ke baad **Warehouses** — sab 22 mockups me linked (Cursor ne poori codebase me bulk sidebar-sync kiya — Phase 1/2/3 files ke sidebar me bhi ab Procurement/Inventory/Manufacturing forward-links hain, jo pehle missing tha).

**Verification pass (Claude, 2026-09-17):**
- Fixed: `warning` color token is-file me galat tha (`#B54708`/`#FFFAEB`/`#FEDF89` — kisi aur file se match nahi karta tha), locked value (`#B45309`/`#FEF3E2`/`#FBD9A5`) se fix kiya, saath hi `neutral` token bhi add kiya (consistency ke liye) aur `.type-qc` badge ka hardcoded hex bhi sahi kiya.
- Confirmed: "Finished Goods" → "FG Warehouse" rename `stock_ledger.html`/`stock_transfer.html`/`stock_adjustment.html` me kiya taaki Warehouse Master ke exact naam se match kare.
- **Resolved (2026-09-17, follow-up verification pass):** "QC Hold" vs "QC Hold Bay" aur "WIP Store"/"WIP Floor" vs "WIP Staging" — poori codebase mein har dropdown option, table cell, aur JS data object check karke Warehouse Master ke exact naam se match kiya (`stock_transfer.html`, `stock_adjustment.html`, `stock_ledger.html`, `material_issue.html`, `production_order.html`, `purchase_return.html`, `gate_inward_grn.html`). Do jagah jaan-boojhkar "QC Hold (virtual)" chhoda (`purchase_order.html`, `material_issue.html`) kyunki wahan ek conceptual/non-standard state represent ho raha hai, literal warehouse nahi.
- **Extra fix mila isi pass mein:** `stock_transfer.html`'s cross-GSTIN example (ST-2025-002) "Main RM (Ahmedabad)" → "Branch FG (Surat)" bata raha tha, jo Warehouse Master ki kisi bhi real entry se match nahi karta tha (aur RM items ko FG warehouse mein bhejna business-logic se bhi ajeeb tha). Fix: destination ko Warehouse Master ki real "Branch RM Store" (Surat) entry se match kiya — jo RM→RM branch transfer hai, zyada sahi story banata hai. Isके liye Warehouse Master ki WH-RM02 (Branch RM Store) ko Stopped se **Active** kiya (kyunki ab ek live transfer isse reference kar raha hai), aur ek naya demo-Stopped row add kiya (WH-OLD1 "Old Finishing Bay") taaki Stopped-state example bhi bana rahe. Filter counts (7 total, 6 active, 1 stopped) update kiye.

---

### Module 8 (gap-fill): Raw Material Category Master — ✅ BUILT (2026-09-17)

**File:** `mockups/raw_material_category_master.html`
**Why added:** Raw Material Master's "Category" field pehle sirf ek chhota inline +Add/Manage picker tha (`erp-list-picker.js` se). User ne explicitly poocha ki Warehouse Master jaisa poora alag master page chahiye — is Claude ke suggestion (chhoti list ke liye inline picker kaafi hai) ke against user ne decide kiya, isliye poora master banaya.
**Fields:** Code, Category name, Description, Active/Inactive (soft-stop only) — Unit Master ka exact pattern (simplest master, toggle-switch status).
**Design notes:**
- Seed data Raw Material Master ke already-used categories se match: Metals, Consumables, Plastics, Components, Packaging (+ ek "Chemicals" — Stopped, demo ke liye).
- Raw Material Master ka Category field ab isi master se "read" karta hai — plain `<select>` + "Manage categories →" link (jaisa Base Unit dropdown pehle se karta tha), inline +Add/Manage hata diya (`erp-list-picker.js` script tag bhi is file se hata diya kyunki ab zaroorat nahi).

### Module 9 (gap-fill): Product Category Master — ✅ BUILT (2026-09-17)

**File:** `mockups/product_category_master.html`
**Why added:** Same reasoning as Module 8, Product Master ki apni Category list ke liye — twin page, sirf data Product-context ka.
**Fields:** Code, Category name, Description, Active/Inactive — same pattern.
**Design notes:**
- Seed data: Wire Harness, Connectors, Packaging, Other (+ ek "Legacy Cable Assembly" — Stopped, demo).
- Product Master ka Category field bhi isi tarah simplify kiya (plain select + "Manage categories →" link, inline picker hataya).
- Dono naye masters (+ Warehouse Master) ab sabhi 24 mockup files ke sidebar me linked hain (bulk sed insertion se, Masters section mein Raw materials/Products ke turant baad).

---

### Biggest catch of the verification pass (2026-09-17): Raw Material Master's codes se poora Procurement/Inventory/Manufacturing chain hi disconnect tha

**Kya mila:** User ne Purchase Order module PRD ke against verify karne ko kaha. Us verification ke dauraan pata chala — **Raw Material Master ke 6 items ka code scheme (`RM-001`..`RM-006`, generic names — Copper Wire 2mm, Solder Wire 60/40, PVC Insulation Sleeve, Heat Shrink Tube 3mm, Terminal Pins Brass, Old Packaging Cartons) poori 15+ files ki Procurement/Inventory/Manufacturing chain (PO, GRN, Inward QC, Purchase Invoice, Purchase Return, Stock Ledger, Stock Transfer, Stock Adjustment, Stock Valuation, BOM, Production Order, Material Issue, Scrap/waste, Consumption Variance) se bilkul match nahi karta tha.** Woh saari files consistently `RM-CU-01`/`RM-CU-02`/`RM-CU-03`/`RM-SW-01`/`RM-PK-01`/`RM-FL-01` use kar rahi thi — in codes mein se ek bhi Raw Material Master mein exist nahi karta tha.

**Vendor names bhi mismatch the:** isi verification mein Purchase Order/GRN/QC/Invoice/Return ke vendor names ("ABC Copper Supplies", "SolderChem Industries", "PackWell Cartons", "WireTech Metals") bhi Vendor Master ke actual vendors ("Shree Copper Traders", "Precision Components Pvt Ltd", "Gujarat Plastics Industries", "Speedway Logistics") se match nahi karte the.

**Decision — kis direction fix karein:** 15+ files ka ek elaborate, aapas mein juda hua story (batch numbers, BOM recipes, QC results, sab RM-CU-01 jaisi codes se linked) tha — Raw Material Master ke 6 generic items usse chhote/isolated the. Isliye Raw Material Master **ko** us badi story se match karaya gaya (1 file rewrite), na ki ulta (15+ files rewire karna).

**Fix kiya (`raw_material_master.html`):**
- Saari 6 rows replace ki: `RM-CU-01` Copper Wire 2mm, `RM-CU-02` Copper Rod 8mm, `RM-CU-03` Copper Strip, `RM-SW-01` Solder Wire 0.8mm, `RM-FL-01` Flux Paste, `RM-PK-01` Carton Box Medium — sab Metals/Consumables/Packaging categories (jo RM Category Master mein already exist karti hain) ke saath.
- Ek naya 7th row add kiya — `RM-OLD-01` "Old Packaging Cartons (Large)" — Inactive/Stopped demo ke liye (jaisa har master mein ek stopped-state example hota hai).
- View-panel ka `RM_DATA` object bhi poora naye codes/descriptions/HSN/reorder-levels ke saath rewrite kiya.
- Filter counts (7 total, 6 active, 1 inactive) aur "Showing X of X" footer update kiye.

**Vendor rename kiya (5 files — `purchase_order.html`, `gate_inward_grn.html`, `inward_qc.html`, `purchase_invoice.html`, `purchase_return.html`):**
- "ABC Copper Supplies" → "Shree Copper Traders" (Gujarat, CGST+SGST — state match)
- "SolderChem Industries" → "Precision Components Pvt Ltd" (Maharashtra, IGST — state match)
- "PackWell Cartons" → "Gujarat Plastics Industries" (Gujarat, CGST+SGST — state match)
- "WireTech Metals" → "Speedway Logistics" (Gujarat, CGST+SGST — state match)
- Display text, dropdown options, table cells, JS data objects, aur search-tokens (data-search/data-vendor attributes) sab update kiye taaki search bhi kaam karta rahe.

**Known follow-up (soft, not urgent):** Purchase Order ke line-items table ka "Amount" column aur Subtotal/Tax/Freight/Grand-total summary abhi bhi static hain, BOM ke Est.-cost jaisa live calculate nahi hote — flag kiya gaya hai, user ne confirm nahi kiya ki abhi fix karna hai ya baad mein.

**Same pattern do aur jagah mila — user ne kaha "sare pages verify kar de":**

1. **Product Master bhi disconnect thi.** `product_master.html` mein `P-001` "Wire Soldering" (variants: Small/2MM, Medium/3MM, Large/5MM) aur `P-002` "Packaging Box" the — jabki poori Manufacturing chain (BOM, Production Order, Material Issue, Stock Ledger, Scrap, Consumption Variance) `FG-WS-01` "Soldered wire assembly" (variants: Standard 1m, Heavy duty 2m) aur `FG-WS-02` "Wire harness" (variant: 3-core) use kar rahi thi. Fix: Product Master ki dono product rows + unke variants + `PRODUCT_DATA` view-object sab naye codes se rewrite kiye (FG-WS-01-STD, FG-WS-01-HD, FG-WS-02-3C SKUs ke saath), Category "Wire Harness" rakhi (Product Category Master mein already exist karti hai).

2. **Machine Master bhi disconnect thi.** `machine_master.html` mein `M-001`..`M-006` (CNC Wire Cutter 1, Auto Solder Rig A, waghera) the — jabki Production Routing (`production_routing.html`) `MC-CUT-01`/`MC-SLD-02`/`MC-ASM-01`/`MC-TST-01` use kar rahi thi (Update-stage panel ka Machine dropdown + har batch ki stage-history). Fix: 4 machines in exact codes se rename ki aur **Active** ki (Routing inhe real batches ke liye live use karta hai, isliye "Breakdown" jaisi status galat thi), 2 baaki machines ko bhi naye naming-scheme se consistent banaya (MC-CUT-02, MC-ASM-02), aur ek naya 7th row (MC-SLD-03) add kiya taaki Maintenance/Breakdown/Retired teeno demo-states bhi ban rahein.

**Verified clean (koi fix nahi chahiye thi):** Unit Master (KG/PCS/MTR jaise generic units — poori codebase se already match karte hain, inherently generic hain), RM Category Master, Product Category Master (dono ke dropdown options RM/Product Master se exactly match karte hain), Customer Master (abhi tak koi Sales-phase file exist nahi karti jo isse reference kare, isliye compare karne ko kuch nahi hai).

**Pattern jo isse seekha:** Phase 1 ke saare 6 original masters (Unit/Machine/Vendor/Customer/Raw Material/Product) Cursor ne/maine alag-alag session mein banaye the, generic placeholder data ke saath — jab baad mein Phase 2/3/4 ki elaborate, aapas mein judi hui story (specific codes/batch-numbers ke saath) banayi gayi, wapas jaake Phase 1 ke masters update nahi kiye gaye the. Yehi wajah thi ki 3 masters (Raw Material, Product, Machine) disconnect nikle — sirf Unit Master bacha kyunki uske "codes" (KG/PCS/MTR) generic hote hain, kisi specific business-naming-scheme ki zaroorat nahi hoti.

---

## 4. Part 2 — Backend (Manual Learning Mode ⭐ — started when user is ready)

**How we work now (2026-09-17):** See **`learning.md`**. AI explains + gives a small snippet; **you type it**. One micro-step at a time. Tracker Current Focus holds the next ID (e.g. `Part2 / Foundation / F2`).

*(Older note: we once built Unit Master backend on 2026-09-15 then removed it to stay mockup-only — see `memory.md`. When Part 2 begins for real, we rebuild with this teach-then-type method.)*

### STEP B — Convert to Flask + Jinja2 (broken into micro-steps)

**What we build (over several teaching steps, not one dump):**
- `run.py` — the file that starts the server
- `app/__init__.py` — creates the Flask app
- `app/units/routes.py` — a route `/units` that renders the page
- `app/units/templates/units.html` — same HTML as the mockup, but now using Jinja2 (still fake/hardcoded data, passed from Python instead of typed directly in HTML)
- `app/templates/base.html` — shared layout (sidebar with links to masters)

**How you review it:** Run `python run.py` in terminal → open `http://127.0.0.1:5000/units` in browser → confirm it looks identical to the mockup.

### STEP C — Database Table + Backend Logic

**What we build:**
- `app/models.py` — a model class per module (e.g. `Unit(db.Model)` with `code`, `name`, `is_base_unit`, `is_active` columns)
- `app/extensions.py` — database connection setup (SQLAlchemy init)
- Routes for add / toggle-status / (edit later): e.g. `POST /units/add`, `POST /units/<id>/toggle`
- Never a hard delete — only `is_active = False` (or the module's own status field), per the core product rule

### STEP D — Connect Frontend to Backend

**What we change:** the template loops over **real** database rows instead of fake hardcoded ones; the Add form and status control actually call the backend routes instead of showing an `alert()` / toast-only mock.

**Acceptance checklist (per module):**
- [ ] Add a new record → refresh page → it's still there.
- [ ] Change status / edit a field → confirm it updates and persists.
- [ ] "Delete" → confirm it soft-deletes (we peek at the database together to confirm the row is still there, just inactive).
- [ ] Duplicate-code / unique-field validation → confirm it's blocked with a clear message.

---

## 5. What Happens After All 6 Modules Are Done

1. **Cross-module review:** Sidebar navigation working across all 6 masters, consistent look, unified Add/Edit/Status pattern.
2. **Auto-Ledger check (Vendor/Customer):** confirm creating a Vendor or Customer also creates a matching ledger entry, per Section 4.3 — a preview of the accounting engine that comes in a later phase.
3. **Demo walkthrough together:** you click through every module, I note anything that feels off.
4. **Only then** do we move to Phase 2 (Procurement/Purchase Cycle) from the master roadmap — reusing everything learned in Phase 1.

---

## 6. Rules We Will Follow Throughout (so nothing surprises you later)

- **No module skips its mockup (Step A).** Even if a module looks simple, we mock it first.
- **No module's backend (Step B onwards) starts until ALL 6 modules' mockups are approved.** (Revised rule, 2026-09-16.)
- **No hardcoded dropdowns.** Every dropdown (like "Unit" inside Raw Material Master, "Category" inside Product Master) pulls from another master's data, never a fixed list baked into the code.
- **No "Rate"/"Price" field on any material/product master** — pricing is always a transaction-time entry, never a master-data field (spec Section 4.4).
- **Every file we create, explained in plain language before/as we build it.**
- **We commit to git after each completed module**, so you always have a working checkpoint. *(We'll set up git when Part 2 starts, if not already initialized.)*
- **If you get an error:** paste the exact error message, and it gets explained, not just fixed — so next time you recognize it yourself.

---

## 7. Phase 1 Status — ✅ COMPLETE (Part 1: Mockups)

All 6 modules built and approved (2026-09-16): Unit, Machine, Vendor, Customer, Raw Material, Product Master.

> **Stale note (2026-10-06):** this section was written before Part 2 began. Phase 1 backend is now done (17 masters) and Phase 2 backend is in progress — see `tracker.md` Current Focus for the live status.

---

## 8. Phase 2 — Procurement, GRN & Inward QC (Mockups)

**Status: 5 mockups built, cross-verified against spec Section 5, minor fixes applied — awaiting final user walkthrough.**

**Why this jumped ahead of Phase 1's backend:** the user wanted to see a full **transaction flow** (not just master-data lists) before committing to any backend, to understand how documents connect to each other. This is a deliberate, discussed deviation from the original "Phase 2 only after Phase 1 backend" plan (see `memory.md`).

**How these were built:** unlike Phase 1 (which Claude built directly), these 5 were built via **Cursor** because Claude's session hit a context limit mid-project. This was a one-off necessity, not a reversion of the "Claude builds mockups" rule — Claude then read and cross-verified all 5 files against the requirements spec and fixed what needed fixing (see below), same as it would review its own work.

### The 5 screens (spec Section 5 — Procurement / Purchase Cycle)

| # | File | Spec ref | What it covers |
|---|---|---|---|
| 1 | `mockups/purchase_order.html` | §5.1 | PO list + New PO (vendor, line items, CGST+SGST/IGST split, freight) |
| 2 | `mockups/gate_inward_grn.html` | §5.1 | Gate inward (challan/transporter/vehicle/gross weight) + GRN, posts to **QC Hold** |
| 3 | `mockups/inward_qc.html` | §5.1 | RM QC templates (per-material parameters), pass/reject qty, Rejection Memo |
| 4 | `mockups/purchase_invoice.html` | §5.2 | Billing capped at **accepted QC qty only**, direct-invoice-without-PO option, TDS 194Q banner |
| 5 | `mockups/purchase_return.html` | §5.3 | Return against a **posted** PI, full/partial qty, reason, debit note |

All 5 share one sidebar (`Procurement` section under `Masters`), and documents cross-link to each other with real `<a href>`s (PO ↔ GRN ↔ QC ↔ PI ↔ Return) — this is the "flow" the mockups exist to demonstrate, e.g. GRN-2025-001's card links back to PO-2025-002, and Purchase Invoice's line items are capped at the QC-accepted quantity, not the GRN-received quantity.

### Verification pass (Claude, against the requirements spec + established design system)

**Confirmed correct / faithful to spec:**
- Fields match spec §5.1–5.3 closely, including exact language (e.g. QC parameter names/tolerances mirror the spec's own copper-wire example: gauge ±0.05mm, purity ≥99.90%, insulation thickness 0.20–0.30mm).
- "Bill only accepted QC quantity" is actually enforced in the UI (`max` attribute on the Bill Qty input, capped to the QC-passed qty).
- "Direct Purchase Invoice" (no PO) path exists, per spec's explicit allowance.
- TDS u/s 194Q banner appears conditionally, matching §1.2.5 / §5.2.
- Purchase Return requires a posted PI, supports full/partial return + reason + debit note, per §5.3.
- No visible Hinglish UI text anywhere (full sweep across all 5 files) — comments are Hinglish, UI text is English, as required.

**Issues found and fixed:**
1. **Color token mismatch** — all 5 files defined a slightly different `neutral` color (`#64748B`/`#CBD5E1`) than Phase 1's Machine Master (`#475569`/`#E2E8F0`), which would make "Draft" status badges look subtly different between Phase 1 and Phase 2 screens. Fixed to match exactly across all 5 files.
2. **Cross-document data inconsistency** — QC-2025-001 (Solder wire) was shown as "Pending" (no result yet), but Purchase Invoice PI-2025-001 (dated a day later) already billed that exact quantity as if QC had passed — which contradicts the app's own "bill only accepted QC qty" rule. Fixed by making QC-2025-001 "Passed" with matching quantities/dates, and updated GRN-2025-001's status from "Pending QC" to "Closed" (both its lines are now fully resolved — one passed, one rejected), including its filter counts and View-panel detail.
3. Removed a stale sidebar comment in `purchase_order.html` referring to not-yet-built pages that now exist.

### What's next for Phase 2

Not yet decided — per the earlier discussion, the user will decide after walking through these 5 screens whether to: (a) go back and build Phase 1's backend (+ Phase 2's, once that's designed), or (b) keep front-loading mockups for more phases first. **Do not assume either direction — ask.**

---

## 9. Phase 3 — Inventory, Warehouse & Stock Valuation (Mockups)

**Status: 4/4 stock mockups + Warehouse Master mock (`warehouse_master.html`, §4.1) — stock screens verified 2026-09-17; warehouse master awaiting user approve.**

**Why ahead of Phase 1 backend:** same as Phase 2 — user wants full visual flow of inventory before backend.

**How these were built:** like Phase 2, built via **Cursor** (session limit), then read and cross-verified by Claude against the requirements spec and Phase 1/2's established design system.

### The 4 screens (spec Section 6 — Inventory & Warehouse Management)

| # | File | Spec ref | What it covers |
|---|---|---|---|
| 0 | `mockups/warehouse_master.html` | §4.1 | Warehouse list/types (RM/WIP/FG/SCRAP/QC_HOLD) — master that stock dropdowns should use |
| 1 | `mockups/stock_ledger.html` | §6.1, §6.3 alerts | Per-warehouse balance + Opening→In/Out→Closing movement ledger panel |
| 2 | `mockups/stock_transfer.html` | §6.2 | WH→WH transfer with transit status (+ E-Way Bill if cross-GSTIN branches) |
| 3 | `mockups/stock_adjustment.html` | §6.3 | Increase/Decrease with reason + approval, physical audit / reconciliation |
| 4 | `mockups/stock_valuation.html` | §6.4 | FIFO / Moving Weighted Average toggle + cost-layer breakdown, WIP note |

All 4 cross-reference the exact Phase 2 document IDs already built (e.g. ledger rows cite `GRN-2025-003 / QC-2025-003`, `PR-2025-003`) — showing continuity between Procurement and Inventory instead of disconnected fake data. Not-yet-built Phase 4/5 references are honestly marked `(mock)`.

### Verification pass (Claude, against the requirements spec + established design system)

**Confirmed correct / faithful to spec:**
- `neutral` color token matches Phase 1/2's locked value exactly in all 4 files (one file even carried a code comment noting it was matched post-Phase-2-fix) — first time a Cursor batch got this right without a fix needed.
- Stock Ledger's movement types (Opening, Purchase, Purchase Return, Transfer, Adjustment, Closing) match §6.1's list; alert badges (OK/Low-reorder/Out of stock/Excess) match §6.3.
- Stock Transfer's transit flow (Draft → Dispatch → In transit → Receive) and cross-GSTIN E-Way Bill requirement match §6.2.
- Stock Adjustment's Increase/Decrease/Physical-audit modes with mandatory reason + approval-before-posting match §6.3.
- Stock Valuation's FIFO/Moving WAVG toggle, per-item cost layers, and "WIP stays valued until FG QC clearance" note match §6.4.
- No visible Hinglish UI text anywhere (full sweep across all 4 files).
- All status-advance buttons (Dispatch/Receive, Submit/Approve) are functionally wired — mutate the row, the underlying JS data object, and filter-pill counts, per the pattern established during the Phase 2 fix.

**Issues found and fixed:**
1. **Sidebar "Manufacturing" section missing/inconsistent** — `stock_ledger.html`, `stock_transfer.html`, `stock_adjustment.html` had no Manufacturing section at all in the sidebar (couldn't navigate to Phase 4 pages); `stock_valuation.html` had a partial one (only the BOM/Recipe link, missing Production order / Material issue / Routing + the two "coming later" placeholders). Added the full, consistent Manufacturing section — matching Phase 4's own sidebar — to all 4 files.
2. **`stock_ledger.html` missing the "Excess Stock" alert filter** — the page's own "Quick help" text cites all 4 alert types from §6.3 (Low/Reorder/Out/Excess), but the filter pills only covered OK/Low/Out. Added an `Excess (0)` filter pill for completeness (no row currently in that state, which is accurate to the mock data).
3. **`stock_valuation.html`'s FIFO layers panel (RM-CU-01) didn't reconcile with `stock_ledger.html`'s full ledger** — found while explaining the "remain" column to the user: the layers panel only listed 3 movements (Opening, GRN-2025-003, ST-2025-001 transfer), summing to 200 KG, but the item's stated Closing Qty is 180 KG (matching Stock Ledger). Root cause: a 4th movement — **Purchase Return PR-2025-003 (−20 KG)**, present in Stock Ledger's full movement log — was missing from the valuation layers array. Fixed by adding it (drawn from the GRN-2025-003 lot, since a return typically goes back against the specific delivery it came from) and recomputing each layer's "remain" correctly per FIFO; now 50 + 180 − 20 − 30 = 180, matching Stock Ledger.

---

## 10. Phase 4 — Manufacturing Engine, BOM, Routing & WIP (Mockups)

**Status: 6/6 mockups built (2026-09-17). Phase 4 manufacturing chain complete.**

| # | File | Spec | What | Status |
|---|---|---|---|---|
| 1 | `mockups/bom_recipe.html` | §4.8 | BOM per variant: RM, consumables, packaging, labor/OH + routing stages | Built |
| 2 | `mockups/production_order.html` | §7.1 | PO + batch/lot, planned qty, linked BOM | Built |
| 3 | `mockups/material_issue.html` | §7 flow | Requisition / issue → Dr WIP \| Cr RM | Built |
| 4 | `mockups/production_routing.html` | §7 | Stage tracker: Cutting → Soldering → Assembly → Testing | Built |
| 5 | `mockups/scrap_waste.html` | §7.3 | Process scrap → Scrap Warehouse | Built |
| 6 | `mockups/consumption_variance.html` | §7.2 | Planned vs actual per material | Built |

All 4 built files cross-link back into Production Order by real `<a href>` (Routing and Material Issue rows link to their `production_order.html` batch), and Production Order's View panel already previews the eventual output split (Good/Rework/Scrap/Rejected per §7.1).

### Verification pass (Claude, against the requirements spec + established design system)

**Confirmed correct / faithful to spec:**
- `neutral` color token matches the locked Phase 1 value in all 6 files.
- BOM/Recipe structure (RM + consumables/packaging + labor/overhead + routing stages, per product **variant**) matches §4.8.
- Production Order's Batch/Lot numbering (`BATCH-WS-YYYYMMDD-NNN`), planned qty, BOM link, and status flow match §7.1.
- Material Issue posts "Dr WIP | Cr Raw Material Stock" and keeps RM lots on the batch for traceability, matching the §7 flow diagram.
- Production Routing's 4-stage pipeline (Cutting→Soldering→Assembly→Testing) with per-stage operator/machine/qty history matches §7's routing description.
- Scrap/waste correctly distinguishes **Saleable scrap** (goes to Scrap Warehouse, becomes stock) from **Process loss** (not stocked, cost-analysis only) per §7.3 — the "Log scrap" form actually hides the warehouse field when "Process loss" is picked, not just cosmetic.
- Consumption Variance's formula (`Variance = Actual − Planned`) and Over/Under/On-plan classification match §7.2; real `<a href>` link back to the specific Material Issue document.
- No visible Hinglish UI text anywhere (full sweep across all 6 files).
- Status-advance buttons (Release/Start/Complete, Post issue, Update stage, Activate BOM, Post scrap, Mark reviewed) are all functionally wired, not decorative.

**Issues found and fixed:**
1. **Sidebar "Procurement" section missing entirely** — all 4 originally-built Phase 4 files jumped straight from Masters to Inventory in the sidebar, meaning a user on any Manufacturing screen had no way back to Purchase Order / GRN / QC / Invoice / Return. Added the full Procurement section (matching Phase 2/3's own sidebar) to all 4 files. (Cursor's later bulk sidebar-sync, done when adding Warehouse Master, re-confirmed this is now consistent everywhere.)
2. **`bom_recipe.html`'s "Est. cost" fields were static, not live** — found while explaining BOM costing to the user: the New BOM form's per-line and total cost fields were hardcoded example numbers with no JS behind them, and critically, **Scrap % wasn't factored into cost at all** (a line showing "2% scrap" still costed only the base qty). Fixed: added a small client-side `ITEM_RATES` lookup table (rates matched to Stock Valuation's FIFO figures where known), and live recalculation — RM line cost = `qty × (1 + scrap%) × rate`, consumable/packaging cost = `qty × rate`, labor/OH = `machine hours × machine rate + labor`, all summing into a live total. Recalculates on every keystroke/line add/remove. This is still pure client-side JS (no backend) — consistent with the Part 1 "mockups only" rule; once Part 2 exists, these rates should come from the real Raw Material master / Stock Valuation engine instead of the hardcoded table. Machine hours deliberately kept as one **combined** figure (not broken into per-stage Cutting/Soldering/Assembly/Testing rows) to avoid scope creep — flagged as a possible future enhancement.
3. **`consumption_variance.html` didn't reconcile with `material_issue.html`** for the same batches — Consumption Variance's "actual" quantities (e.g. MI-2025-001: Copper 25.4 KG, Heat-shrink 498 PCS) didn't match Material Issue's own "issued" quantities for those exact lines (which showed 25 KG and 500 PCS — i.e. no variance at all, contradicting the very page meant to analyze variance). Also, MI-2025-002 was missing 2 lines (Flux paste, Carton box) that Consumption Variance's MI-2025-002 report assumed existed. Fixed by updating `material_issue.html`'s issued quantities to match Consumption Variance's figures, adding the missing lines, and correcting the list table's stale "Lines: 6" count to the accurate "4". Known minor follow-up (not fixed): `bom_recipe.html`'s BOM-002 recipe itself lists a 3rd RM line (Copper rod) and Heat-shrink (not Flux) as a consumable — neither Material Issue nor Consumption Variance fully matches BOM-002's exact recipe list; low-visibility, not addressed in this pass.

---

## 11. Immediate Next Action

> **Stale note (2026-10-06):** this was the plan as of 2026-09-17 (mockup walkthrough). Backend work has moved far past it — the live "next step" is always `tracker.md` → Current Focus.

Phase 1 (now 7 masters, including the gap-fill Warehouse Master) + Phase 2, 3, and 4 mockups (16 screens: 5+4+6) are all built and verified (2026-09-17). Walkthrough / next phase with user —

```
Masters:        (existing 6) + Warehouse Master
Procurement:    Purchase Order → Gate Inward/GRN → Inward QC → Purchase Invoice → Purchase Return
Inventory:      Stock Ledger → Stock Transfer → Stock Adjustment → Stock Valuation
Manufacturing:  BOM/Recipe → Production Order → Material Issue → Routing → Scrap → Consumption variance
```

— so every screen's fields and buttons are understood in terms of *why*, not just *what*, before any backend work starts. **Do not assume the direction — ask.**

---

## 12. Client Meeting Adjustments (2026-09-29/30) — New Requirements

**Source:** `Manufacturing_ERP_Unified_Requirements_Specification.md` Section 10 (§10.1–§10.12) — a client feedback session added 12 architectural refinements to the spec. This section maps each one onto the project's *actual current state* (Phase 1 backend ~complete, Phase 2 Purchase Order/GRN/Inward QC backend in progress) rather than repeating the spec text — see the spec doc itself for full field-level detail.

**Manual Learning Mode is unchanged for all of this** (`CLAUDE.md` §0A, `learning.md`): AI builds templates/HTML directly and teaches Flask one micro-step at a time; user types the Python. Same scoped exceptions as before (AI fixes small bugs when asked "fix karo").

### 12.1 Status of each item (updated 2026-10-03 — most of this list has since moved; see note below)

> **Note (2026-10-03):** Items 2, 3, and 12 below were "in progress"/"decision-pending" as of 2026-09-30 and are now **done** (built across several sessions 2026-10-01→03, reviewed by Claude 2026-10-03 — see §12.4). This table is kept as the original record of what the client meeting asked for; read `tracker.md` Current Focus for what's actually true today.

| # | Spec ref | Item | Status / plan |
|---|---|---|---|
| 1 | §10.1 | Zero hardcoded dropdowns everywhere | Standing rule, reinforced further: the old `INDIAN_STATES` hardcoded list is now fully gone, replaced by a real State Master (`states` table). Vendor Type and Payment Terms also converted from hardcoded option lists to real masters (§10.3 below). |
| 2 | §10.2 | **Charges Master** — simplified: Code (auto) + Name + Status only | ✅ **Done (2026-10-01).** Full CRUD typed + verified (`scratchpad/verify_charges_fix.py` 5/5 PASS). Now also used as PO's line-level Charges (Add/Minus effect), replacing the old flat `freight` field — see §12.4. |
| 3 | §10.3 | Universal auto-generated codes on **all** masters/transactions | ✅ **Done for 12 of 14 masters** (2026-10-02, `tracker.md` Work Log): Vendor `V-`, Customer `C-`, Warehouse `WH-`, Machine `MC-`, Work Stage `WS-`, RM Category `RMC-`, Product Category `PC-`, Raw Material `RM-`, Charges `CHG-`, State `ST-`, Vendor Type `VT-`, Payment Term `PT-`, Product `FG-`. Existing rows were renumbered to match (`scratchpad/renumber_master_codes.py`, DB backed up first). **Deliberately excluded: Unit, Tax Rate** — their codes carry real meaning (`KG`, `GST18`), not a serial, per `memory.md`. |
| 4 | §10.4 | Vendor/Customer real document upload | ✅ **Done (2026-10-06), built by Claude directly** (user explicitly asked — scoped exception to Manual Learning Mode, `CLAUDE.md` §0A). Shared `PartyDocument` model + `app/party_documents/` blueprint (list/add/delete/download, used by both Vendor and Customer via a `party_type` param so the logic isn't duplicated) + a "Documents" section in both View panels (AJAX upload/list/delete, no page reload). 5MB size limit + PDF/PNG/JPG check enforced server-side. Verified with a full-app regression sweep (all 20 no-arg list pages) — no breakage from the shared `models.py`/`__init__.py` changes. |
| 5 | §10.5 | PO "Confirm" → vendor invoice/bill upload modal before Draft→Open | ✅ **Done (2026-10-03).** Confirm now opens a modal (file required, invoice no./date optional) instead of submitting instantly; `PurchaseOrder` gained `vendor_invoice_no`/`vendor_invoice_date`/`vendor_invoice_file`; files land in `instance/uploads/purchase_orders/<po_id>/` (new `UPLOAD_FOLDER` config, gitignored); a `purchase_orders_invoice` route serves them back for viewing. First file-upload feature in the project — see `tracker.md` for the 5 bugs this surfaced (including a Windows-backslash-vs-`send_from_directory` path bug worth remembering for any future upload feature, e.g. §10.4's vendor/customer documents). |
| 6 | §10.6 | Two-tier "Pending Action Queue" + "Completed Register" on every operational stage | **Still not started.** |
| 7 | §10.7 | Partial deliveries: `received_qty`/`remaining_qty`/`billed_qty` per PO line, PO status state machine | ✅ **Core done (2026-10-03).** `received_qty`/`remaining_qty` are computed properties (not stored columns) on `PurchaseOrderLine`; `refresh_po_status()` in `app/grns/routes.py` moves `PurchaseOrder.status` through `Open → Partial → Closed` whenever a GRN is added/posted, reusing the single-word status names the UI's badge CSS already expected. The over-receipt warning popup on the GRN form (built earlier) already used the right math and needed no change. **Not done: `billed_qty`** (that's Purchase Invoice's job — Phase 2 Module 4, not a §10.x item, still not started). **`[Short Close PO]` is now also done (2026-10-06)** — see `tracker.md`. |
| 8 | §10.8 | Unified Procurement Document Docket | **Still not started**, depends on #4/#5. |
| 9 | §10.9 | RM lot code + unit-level serialized barcode/QR | **Still not started — fully deferred, not even the GRN-side internal lot code.** Discussed 2026-10-06: considered adding just an internal lot-code field at GRN time (ahead of the actual barcode printing, which needs Purchase Invoice to exist first), but decided against it — it would sit unused with zero consumer until Purchase Invoice + QC-triggered printing exist, which is exactly the "design for a hypothetical future requirement" this project avoids. Revisit this whole item once Purchase Invoice is built. |
| 10 | §10.10 | Printed document footer: "Created By"/"Approved By" attribution | **Still not started** — note a print template *does* now exist (`purchase_order_print.html`, §12.4) but without this attribution block; easy to add when this item is picked up. |
| 11 | §10.11 | Visitor Gate Pass | **Deferred**, unchanged. |
| 12 | §10.12 | **Recipe-Based Product Formulation** | ✅ **Resolved and built (2026-10-01→03)** — not by replacing Product+Variant as the spec literally suggested, but by a cleaner compromise the user locked in 2026-10-01/02 (full reasoning in `memory.md`): `ProductVariant` table is kept (not dropped) but no longer exposed in the UI; each Product now carries its own `attributes` (JSON) and recipe (`VariantRecipeItem.product_id`) directly, with the product's **name auto-built** from its category + attribute values (no free-text name entry, no duplicate specs). See §12.4. |

### 12.2 / 12.3 — superseded

The "immediate next module: Charges Master" and "GRN over-receipt fix" notes that lived here (written 2026-09-30) are both stale — Charges is done (see §12.1 row 2), and the GRN fix is simply tracked as open item §10.7 above (row 7), not a separate note. Removed to avoid two sources of truth; see `tracker.md` for the live version of both.

### 12.4 What actually got built 2026-10-01→03 (reviewed by Claude 2026-10-03)

This wasn't just the 12 client-meeting items — real scope grew along the way. Full detail is in `tracker.md`'s Work Log (search "2026-10-01" through "2026-10-03"); summary:

- **Product Master rework** (§10.12, resolved as above) — `products/routes.py` and `products.html` both substantially rewritten. Variant Add/Edit/Delete routes are commented out (not deleted) in `products/routes.py`, kept as reference. One loose end: no migration yet drops the now-unused `ProductVariant`/`variant_id` plumbing — it just sits unused in the DB (1 leftover row). Low priority.
- **Three new masters**: State (`states`, GST 2-digit code stays manual/government-assigned, everything else auto), Vendor Type, Payment Terms — all replacing what used to be hardcoded `<option>` lists on Vendor/Customer/PO forms.
- **Universal auto-code retrofit** across 12 masters (§10.3, row 3 above).
- **Purchase Order gains a Charges system** (`PurchaseOrderCharge`, many-to-one against the Charges Master, each line tagged `add`/`minus`) replacing the old single `freight` field for all *new* POs, plus a print view (`/purchase_orders/<id>/print` → `purchase_order_print.html`, A4 letterhead with the company's real name/GSTIN/address hardcoded directly in the template — no Company Master exists yet to source it from).
- **New Production Order module** (`app/production_orders/`) — choose a product, give a quantity, its recipe copies onto the order (ratio × qty, converted to KG via `unit_weight` for non-KG products) plus optional "extra material" lines for things like packaging that aren't part of the recipe ratio. Explicitly *not* wired to Material Issue yet (that's Phase 4, intentionally deferred — see `tracker.md` 2026-10-02 "User ne Material Issue roka").
- **Sidebar reorganized** into sub-groups (Common / Production / Raw material / Products / Storage / Partners) — navigation-only, no route changes.

**Claude's review pass (2026-10-03) found no live-breaking bugs.** Four low-severity items worth knowing about (all detailed in `tracker.md` Current Focus and `memory.md`): a migration backfill gap for old recipe rows (harmless today, only 1 product exists), one leftover dead code branch in `warehouses_add`, the `PurchaseOrder.freight` field being quietly dead for new POs now that Charges replaced it (old POs still display correctly), and no duplicate-raw-material guard between a Production Order's recipe lines and its "extra material" lines.
