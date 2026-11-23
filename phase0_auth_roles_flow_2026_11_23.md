# Phase 0 — Login + simple Roles / Permissions (Developer > Admin > Staff) — FLOW (2026-11-23)

**Status: FLOW PROPOSED — user ke OK ke bina kuch build nahi hoga.** Yeh file `tracker.md` Current Focus aur `memory.md` se linked hai.
Research ka source: 3 read-only researchers (code inventory, saari md files, secure-design research) — 23 Nov 2026. Sab numbers neeche asli code se hain (`app.url_map` dump).

---

## 1. Requirement (user, 23 Nov 2026 — apne shabdon me)
1. Sabse pehle ek **Admin account**; wo **users / roles / permissions manage** kare.
2. Role / permission **module-wise**: jaise Sales module → uske jitne page, un page ki permission do → user ko **wahi module / page dikhe jiski permission ho**.
3. **Ekdum simple** role / permission aur **simple UI / UX** (ERP ke liye).
4. Admin ke upar ek **Developer account** (user ka apna) — jo **Admin ko bhi permission de sake**.
5. Baaki cheezein baad me sochenge — abhi sirf itna, flow research karke.

## 2. Abhi app ki sachchi halat (code se, 23 Nov)
- **Koi login nahi, koi User/Role table nahi, koi before_request nahi.** Portal link wale kisi ko bhi khula hai. 238 url rules = 82 GET + 154 POST + home + static (critic ne recount kiya). 47 blueprints, koi url_prefix nahi.
- **Sidebar = hardcoded HTML** (`app/templates/base.html` lines 119–225), 47 links, koi loop / menu data nahi. Har link `url_for('bp.endpoint')`.
- **Free-text "kisne kiya"** (issued_by, tested_by…) form me type hota hai, user se juda nahi. `created_by / approved_by` kahin nahi. (Ye is step me NAHI chhedenge.)
- `SECRET_KEY` ka fallback public dev key hai (`app/__init__.py:62`) — live par real secret ke bina login safe nahi.
- CSRF protection kisi POST par nahi (154 POST). Login aate hi iska hona zaroori hai.
- Python server par **3.9** hai (local 3.11) — nayi libraries / syntax 3.9 ke hisaab se.
- Dashboard ke 5 routes + 10 aur jagah **fetch/JSON** hain — unauthenticated par HTML login redirect nahi, **JSON 401/403** chahiye warna page ka JS toot jaata hai.

## 3. Design — 3 line me
1. **3 type ke account:** **Developer** (hidden, owner) > **Admin** > **Staff** (kisi Role ke saath).
2. **Role = pages ki list + har page par level:** `No access / View / View + Edit`. (GET = View, POST = Edit — code check: koi GET kuch commit nahi karta, isliye ye rule safe hai.)
3. **Ek jagah se enforce:** ek `before_request` guard — har request par endpoint → page key → user ka level. **Deny-by-default** (jo map nahi, wo band). Sidebar sirf permitted links dikhata hai (par asli suraksha guard hai, sidebar sirf UX).

### 3.1 Teen account types — kaun kya kar sakta hai
| | Developer (owner) | Admin | Staff |
|---|---|---|---|
| Kaise banta hai | **Sirf server command** (`flask create-developer`), web se kabhi nahi | Developer banata hai (ya Developer ke diye ceiling me Admin khud) | Admin / Developer |
| Sab pages | Haan, hamesha (check bypass) | Sirf jo Developer ne Admin ko diye ("Admin ceiling") | Sirf apne Role ke |
| Users / Roles pages | Haan | Haan | Nahi (kabhi assign nahi hote) |
| Admin ko pages dena | **Haan** — "Admin access" page | Nahi | Nahi |
| Role bana ke staff ko dena | Haan | Haan, **par sirf wahi pages jo Admin ke paas khud hain** (apne se zyada nahi de sakta) | Nahi |
| Dikhta hai? | Admin ko **kabhi nahi** (user list, audit, counts sab me chhupa; by-id kholne par 404) | Developer ko dikhta hai | Admin ko dikhta hai |
| Deactivate / password reset | Sab ka | Sirf Staff ka (apne se neeche) | — |

### 3.2 "Module-wise" ka matlab (UI me)
Role editor me **sidebar jaise hi module headers**: Dashboard · Masters · Procurement · Sales · Inventory · Manufacturing (+ Administration, sirf Developer ko). Har module ke andar uske pages ki rows, har row par ek **3-way chip**: `No access | View | View + Edit`. Har module par "Set all" ek click. Neeche **sticky Save bar** ("N changes"). Bas.

### 3.3 Pages ki list (47 sidebar pages = 47 permission keys)
| Module | Pages (key) | # |
|---|---|---|
| Dashboard | dashboard | 1 |
| Masters | units, tax_rates, charges, states, payment_terms, payment_modes · work_stages, machines, production_lines · rm_categories, raw_materials · product_categories, products · warehouses, racks · vendors, vendor_types, customers | 18 |
| Procurement | purchase_orders, grns, inward_qc, purchase_invoices, purchase_returns | 5 |
| Sales | quotations, dispatch, invoices, receipts, sales_returns, receivables, statement, profit | 8 |
| Inventory | stock (ledger), opening_stock, stock_transfers, stock_adjustments, valuation, finished_goods | 6 |
| Manufacturing | production_orders, production_planning, material_plan, material_issues, routing, production_output, scrap, variance, costing | 9 |
| Administration (naya) | users, roles (+ Developer ke liye: admin_access, audit_log) | 2–4 |

**Page key = us page ka list endpoint.** Jo URL sidebar me nahi (jaise `/quotations/<id>`, `/scrap/types`, `/inventory/stock/<lot>`, print pages, file links) wo **apne parent page ki permission** se chalte hain (View = dekhna / print, Edit = badlana).

### 3.4 Wo jagah jahan "blueprint = module" rule toot-ta hai (registry me explicit mapping)
1. **Finished goods** `/finished_goods` — blueprint `production_output` me, sidebar Inventory me → alag key `finished_goods`.
2. **Stock ledger vs Stock valuation** — dono `inventory` blueprint me, par valuation cost dikhata hai → **alag keys** (`stock`, `valuation`).
3. **party_documents** (4 routes, vendors + customers dono ka document panel) → party type ke hisaab se `vendors` ya `customers` ki permission (delete / file route doc se party type nikalte hain).
4. **Production planning page** production_orders ke move / release / start ko POST karta hai → registry me ek endpoint ke **kai page** likh sakte hain; user ke paas **inme se kisi ek ka Edit** ho to chalta hai (taaki planning wale ke apne buttons 403 na dein).
5. **purchase_invoices → purchase_returns_add**, **production_output → material_writeoff_add**, **material_plan → create_po**: wahi "host page ka Edit" rule.
6. **Dashboard** ke 5 JSON routes: 2 GET (`machine_detail`, `machine_assign_check`) → `dashboard` **View**; 3 POST (Assign & Start, queue, move) → `dashboard` **Edit**. (Dhyan: `machine_assign_check` GET hai par andar tentative DB write + rollback karta hai — section 10 dekho.)
7. **tour / demo** (`/demo`, `/tour/*`, jo demo orders banate hain): **Developer-only** (live par normal users ko nahi).
8. **Naming ki ulajhan** (registry sambhalega): `purchase_return_list` (singular), `invoices` = sales_invoices blueprint, `receivables` = aging blueprint, `statement` = customer_statement.
9. **File routes (6)** — party doc file, PO invoice, inward QC report, quotation PO file, routing TC, scrap photo — normal routes hain, isliye guard inhe bhi cover karta hai (uploads folder static se nahi khulta).

## 4. Security basics (chhote par zaroori — research se)
| Cheez | Faisla (recommended) |
|---|---|
| Login library | **Flask-Login 0.6.3 sirf plumbing** (user_loader, current_user). Permission logic apna. `remember me` **nahi**. |
| Password | `werkzeug.security` (pehle se installed). Server par `hashlib.scrypt` check; na chale to `pbkdf2:sha256`. Password kahin print / log / md me nahi. |
| Session cookie | HttpOnly, SameSite=Lax, **Secure env-switch se** (`ERP_HTTPS=1` sirf live par, warna local http par login hi nahi chalega). ProxyFix (LiteSpeed ke peeche). **Idle 60 min**, absolute 12 h. |
| Secret key | Live par `ERP_SECRET_KEY` **zaroori** (set na ho to app start hi na ho). |
| CSRF | **Flask-WTF `==1.2.2` pinned** (1.3.0 ko Python 3.10 chahiye, server 3.9 hai). `base.html` me meta tag + ek chhota JS (har form me hidden token, har fetch me header). Token time-limit None (khula drawer 1 ghante baad bhi chale). |
| Lockout | 5 galat try → 15 min lock (account par, DB me). Hamesha ek hi message "Invalid username or password". Admin "Unlock" kar sakta hai. |
| First login | Naye user / reset ke baad **password badalna zaroori** (temp password Admin ko ek baar screen par dikhta hai, email nahi). |
| Revoke | `users.session_version` — Admin deactivate / reset / role badle to uske purane session agli request par band. |
| Delete | User / Role **kabhi hard delete nahi** — Active / Inactive. Aakhri Admin ko deactivate nahi kar sakte. |
| Audit (minimum) | Login / logout / failed login, user + role + permission ke badlav: kaun, kab, kya. (Business documents par created_by — **abhi nahi**.) |
| Developer bootstrap | `flask create-developer`, `flask reset-password`, `flask unlock-user` — sirf server shell se (isliye web se koi escalate nahi kar sakta). |

## 5. Screens (sirf 3–4 nayi, baaki ERP jaisa hi)
1. **Login** — username + password, ek hi error. Logo + simple card. (`base.html` se alag template; sidebar / stock-alert query nahi.)
2. **Users** (Administration) — table: name, username, role dropdown, Active/Inactive chip, last login · buttons: Add user · Edit · Reset password · Unlock · Deactivate. Create form: name, username, role, **temp password (auto, ek baar dikhta)**.
3. **Roles** (Administration) — list (role, kitne users, Edit permissions · **Copy** · Deactivate) → **Role editor = matrix** (3.2). Shuruaati 6 editable template roles (seed): *Store keeper, Purchase, Sales, Production supervisor, Accounts, Read-only* (roles DB rows hain, hardcoded nahi — spec ka "dynamic-first" rule).
4. **Admin access** (sirf Developer) — Admin ke liye wahi matrix (ye Admin ki "ceiling"); Admin role editor me jo pages Admin ke paas nahi, wo **grey + "Ask the developer"**.
5. **Audit log** (sirf Developer / baad me Admin ko option) — read-only list.
6. **403 page** — normal layout me: "You do not have access to <Page>. Ask your admin." + Dashboard button. Fetch calls ko toast (`erp-toast.js`).
7. **Sidebar** me ek "Administration" group (sirf jise permission) + neeche user ka naam + Logout + Change password. Khaali module header chhup jaata hai. Login ke baad `/` **pehle permitted page** par jaata hai (abhi hardcoded `units` — wo bina Units permission wale ko 403 deta).

## 6. Scenarios (inka auto-test banega)
1. **Pehla deploy:** migration → `create-developer` → Developer login → Admin account banao → Developer ne Admin ko pages diye → Admin ne role + staff banaya. (Is order ke bina live par sab lock ho jaata hai — deploy me yahi sequence.)
2. Staff login → sirf apne module / pages sidebar me; baaki gayab.
3. Staff ne **URL type karke** bina permission wala page khola → 403 (backend), sidebar se kuch lena-dena nahi.
4. **View-only** user ne crafted POST bheja → 403, kuch save nahi.
5. Fetch / JSON route par session expire → **JSON 401** (HTML redirect nahi), page ka JS "Session expired, please login" toast dikhata hai.
6. Admin ne role me aisa page tick karna chaha jo uske paas nahi → greyed; crafted request bheja to server refuse.
7. Admin ne user list / by-id URL se **Developer** ko dekhna chaha → nahi dikhta / 404; audit me bhi nahi.
8. Admin ne user deactivate kiya → uska khula session agli request par logout.
9. 5 galat password → lock 15 min; Admin Unlock; sahi password se login.
10. User password bhoola → Admin reset → temp password ek baar → user login par naya password set karta hai.
11. Aakhri Admin deactivate → refuse (Developer kar sakta hai).
12. Role jisme users hain, delete nahi (sirf Inactive) / role ke users ko kya hoga: Inactive role wale user login nahi kar paate.
13. Role ke permissions badle jab user logged-in → **agli request par asar** (har request par DB se).
14. Production planning wale user ko "Release / Start" buttons chalte hain (multi-page endpoint rule), production_orders page nahi dikhta.
15. File link (PO invoice, TC, scrap photo) bina permission ke → 403; permission ho to khulti hai.
16. Print page — View wale ko khulta hai (parent page ka View).
17. Dashboard auto-reload (`setInterval`) par session expire → login page par jaata hai; **shop-floor wall screen** ka sawal (Q5).
18. Logout ke baad Back button → login par bhejta hai; copy kiya hua purana cookie `session_version` se band.
19. Naya blueprint / route jo registry me nahi → **deny** (ek self-check test jo har `url_map` rule ko map se milata hai, warna fail).
20. Developer ka password kho gaya → server par `flask reset-password`.
21. Do Admin ek hi role edit karein → aakhri Save jeetta hai (audit me dono dikhte hain).
22. Local `http://127.0.0.1` par login chalta hai (Secure cookie env-switch).

## 7. Jo is step me **nahi** hoga (aapne kaha "baad me")
- Multi-tenancy / Company-Branch, MFA, Department master, approval matrix (amount-based), full "old / new JSON + IP" audit.
- **Field-level secrecy** (cost / profit / customer name kisi allowed page ke andar) — page-level permission ke liye Costing, Sales profit, Stock valuation, Consumption variance pages poore chhupa sakte hain, par cost numbers **dusre pages ke andar** (production output, finished goods, invoice, quotation warning, stock lot) tab tak dikhte rahenge jab tak alag "Can see cost" flag nahi banta.
- **Action-level special rights**: *Loss-invoice Owner approve* (`/invoices/<id>/approve`), *Cross-line Assign & Start* (Production manager only), *borrow stock Owner approval*. Is step me ye "us page ka Edit" se chalenge. Aage ek chhoti "Special permissions" list (3–4 checkbox) pe plan.
- `created_by / approved_by` har document par, print par "Prepared by".
- Per-user overrides, ek user ke kai roles, data scope (sirf apni warehouse / branch).

## 8. Build order (har step: auto-test + tracker; user ke "aage badho" par)
- **P0-1** Models + migration: `users`, `roles`, `role_permissions`, `audit_log` (+ seed 6 starter roles, `kind`, `session_version`, `failed_count`, `locked_until`, `must_change_password`). Backup pehle.
- **P0-2** CLI: `create-developer`, `reset-password`, `unlock-user`. Security config (secret key check, cookie flags, ProxyFix). Flask-Login + Flask-WTF(1.2.2) install (requirements pin).
- **P0-3** Login / Logout / Change-password + standalone login page + first-login rule + lockout + audit rows.
- **P0-4** **Guard**: page registry (47 keys + Administration + extras mapping 3.4) + `before_request` (deny-by-default, JSON 401/403, GET=View / POST=Edit) + `can()` template helper + 403 page + home redirect. **Self-check test** (har url_map rule mapped). *Yahin sabse zyada dhyan; poora app isi ke peeche jaata hai.*
- **P0-5** CSRF wiring: `base.html` meta + 1 JS (form hidden input + fetch header); saare 154 POST forms / fetch ek ek check (onchange submit wale bhi).
- **P0-6** Sidebar: `can()` se links + empty headers hide, user name + Logout, Administration group.
- **P0-7** Admin screens: Users, Roles (matrix editor + Copy), Admin access (Developer), ceiling / rank rules, "Show inactive", Audit log.
- **P0-8** Poora regression (saare purane test scripts ek logged-in test client ke saath), beta / staging copy par full sweep, **phir** live deploy (sequence scenario 1) — user ke word par.

Har step ke baad **DB copy par auto-test**; browser demo sirf P0-4 / P0-7 ke baad ek baar (user: "quick, auto-test"). Teaching mode: abhi tak ke builds jaise **AI likhta hai + har step samjhata hai, user review karta hai** (CLAUDE.md §0A ka default "user type kare" alag hai — user confirm kare).

## 9. User se tay karne wali cheezein (har ek ke saath meri recommendation)
1. **Levels:** `View / View + Edit` (recommended) ya sirf ek checkbox "Allowed"? — View-only user (jaise accountant ko stock dekhna) tabhi ban sakta hai.
2. **Admin ceiling:** Developer tay kare Admin ko kaun se pages milenge, aur Admin usse zyada kisi ko na de sake? (recommended: haan)
3. **Administration pages** (Users / Roles) kabhi staff role ko assign na ho — sirf Admin / Developer? (recommended: haan)
4. **Starter roles** (Store keeper, Purchase, Sales, Production supervisor, Accounts, Read-only) seed karein, editable? (recommended: haan)
5. **Idle timeout 60 min** theek? Koi **TV / shop-floor dashboard screen** hai jo din bhar login rakhni hai? (agar haan to uske liye alag long-session "Display" user — baad me)
6. **Login ID:** username (recommended) ya email?
7. **Audit log** abhi sirf Developer ko dikhe? (recommended) Admin ko baad me option.
8. **Tour / demo player** live par Developer-only? (recommended)

---

## 10. Do independent critics ke baad pakke changes (23 Nov) — jahan upar se alag hai, **yahi maana jaayega**
Do read-only critics (security + completeness) ne flow ko asli code se milaya: 15 + 8 findings. Verdict: *core idea (ek guard, deny-by-default, registry self-check) sahi hai; asli khatra registry ke aas-paas ki cheezein hain.* Sab neeche flow me daal diye:

### 10.1 Admin ceiling ka hole (HIGH) — "Admin staff ban ke ceiling tod sakta hai"
Admin temp password dekhta hai, staff reset kar sakta hai, role copy kar sakta hai — to wo kisi aise Staff ka role le ke wo page khol sakta hai jo uske ceiling me nahi. **Fix:** ek hi helper `can_manage(actor, target)` + `clamp_permissions(actor, requested)` har Users / Roles route me: Admin sirf us Staff ko **create / role assign / reset / unlock** kar sake jiske role ka har page + level uske ceiling ke andar ho; role dropdown isi se filter; **Copy** clamp hoke shuru; Developer ceiling kam kare to jin roles me ab zyada hai unhe flag + runtime clamp. **Admin account sirf Developer banata hai** (pehle "ya Admin khud" tha — hata diya). Ceiling ka data **alag table** me (normal role-edit route se na dikhe). Administration keys (users, roles, admin_access, audit_log) kabhi kisi Staff role me nahi — server whitelist, aur guard ye pages **user kind** se tay karta hai, permission row se nahi. Har login par IP + user-agent audit me.

### 10.2 Secret key / cookie fail-open (HIGH) — **defaults ulte**
Dev key aur non-Secure cookie **sirf jab `ERP_DEV=1`** ho. Warna: key na ho ya 32 char se chhota → app start hi na ho (par `flask db upgrade` / `create-developer` jaise CLI par ye check skip). Cookie `Secure=True` by default, alag cookie name (portal parent domain share karta hai). Cookie me sirf `id + session_version + login_ts`, sab DB se verify. Phase 0 ke baad live ki secret key **rotate** (purani key git history me thi jab repo public tha).

### 10.3 Deploy se lock-out (HIGH) — deploy ke liye alag step list
(1) Deploy script ka health check + 54-page staging sweep abhi bina login chalta hai — guard ke baad sab 302/401 → **auto-rollback**. Tooling ko test Developer user se login karana hoga (ya public check me 302 accept). (2) Health sirf GET hai — **ek asli login POST public hostname se** deploy ke baad. (3) `ProxyFix(x_for=1, x_proto=1, x_host=1)` pin; CSRF referer-strict LiteSpeed ke peeche beta par pehle test. (4) CLI **service user (`porta1691`) se** chalao, root se nahi (root-owned DB journal → "readonly database"). (5) `requirements.txt` me Flask-Login + Flask-WTF==1.2.2 + **server par pip install step**. (6) Break-glass: `reset-password` + rollback bina web UI ke.

### 10.4 "GET = View, POST = Edit" ke 2 apwaad → registry me **har endpoint ka explicit minimum level**
`dashboard.machine_assign_check` GET hai par andar tentative write + rollback (SQLite write-lock pakadta hai) → **Edit**; `production_orders.expected` POST hai par sirf preview → **View**; `quotations.quotations_new` GET form hai → **Edit**. SQLite: **WAL + busy_timeout=15000** (engine connect event) taaki login / audit writes "database is locked" na dein. Login / audit write chhota, ek transaction.

### 10.5 Lockout — DoS + enumeration + race
Sirf account par hard-lock = attacker Admin / Developer ko hamesha lock rakh sakta hai. **Fix:** counter `(username, IP)` par + progressive delay; **Developer kabhi hard-lock nahi** (sirf delay); unknown / locked / inactive user par bhi dummy hash (timing same), sab message same; counter DB me **atomic** `UPDATE … failed_count = failed_count + 1` (2 workers, in-memory nahi); LiteSpeed par `/login` rate-limit. scrypt 2 workers ko bhookha na kare — login par global concurrency / rate limit.

### 10.6 Chhote par zaroori
- **Login / 403 page par stock-alert query nahi**: `alert_count` context processor lazy + sirf logged-in aur `can('stock')` ho tab. 403 page ka minimal layout.
- **Developer chhupa rehna:** ek `visible_users(viewer)` + `get_visible_user_or_404` har query / count / dropdown / audit join me; username "already exists" error generic; admin URLs me sequential id nahi (uuid / hash); grey-out text "Not available for your account".
- **Session:** logout par `session_version` bump (ya 12 h window ka sachcha faisla), apna password badalne par bump; **dashboard auto-reload / polling idle timer refresh na kare**; har authenticated response par `Cache-Control: no-store, private` + `Vary: Cookie` (LiteSpeed cache off confirm).
- **Temp password** redirect / flash se nahi (cookie me chala jata) — seedha POST response me, `no-store`. CLI me `getpass` / hidden prompt (argv nahi). Min length 10, temp password dobara nahi.
- **Login `next`:** sirf relative path (`/` se shuru, `//` nahi), phir `can()` se dobara check, warna pehla permitted page. **Logout = POST + CSRF.** Headers: `X-Frame-Options: SAMEORIGIN`, `X-Content-Type-Options: nosniff`.
- **CSRF traps:** token sirf `method=post` forms me (8 GET filter forms ke URL me token leak na ho); runtime banaye forms (customers.html, vendors.html) + 22 `.submit()` calls ke liye `HTMLFormElement.prototype.submit` patch + delegated listener; fetch wrapper ek hi baar; **JSON vs HTML 401** request path-prefix / apne header se tay ho (Accept se nahi); guard CSRFProtect se pehle, `CSRFError` anonymous par 401.
- **Tour / demo:** `ERP_DEMO=1` env flag ke peeche, live par **off** (fake TC letterhead ke saath compliance risk). `tour_shortage_order` ka andar wala `test_client().post` hata ke seedha order-banane wala function. Test client ke liye guard / CSRF bypass **kabhi nahi** (testing ke liye alag test-login hook).
- **Maker-checker:** `stock_adjustments/approve` (aur production_orders review, variance review, stock_transfers receive, PO confirm) — Edit wala apna hi submit + approve kar leta. Abhi `approve` ko **alag key** (shuru me Developer / Admin only) aur **koi starter role Edit(submit) + approve dono ke saath seed nahi**. Baaki "Special permissions" baad me.
- **Dashboard Edit** wide hai (order + stage Start kar sakta hai, `persist_schedule` sab non-frozen orders ki dates likhta hai) — Role editor me tooltip "Dashboard Edit can start orders".

### 10.7 Registry me jo chhoot raha tha (completeness critic, `app.url_map` se)
**35 non-sidebar GET endpoints ka page key** (poori mapping build me registry file me): print pages → parent ka View (statement, dispatch, material_issues ×2, production_orders, production_output, purchase_orders ×2, quotations, receipts, invoices, sales_returns, routing TC, scrap label ×2); file routes (PO invoice, inward_qc report, quotation PO file, routing TC, **routing.scrap_photo → routing** (scrap nahi), party doc file → vendors / customers); JSON helpers → apna page View (grns.po_lines, inward_qc.grn_lines, raw_materials qc_parameters, party_documents list, dashboard machine_detail); detail pages → parent; `warehouses_branches_add` (POST) → warehouses. Tour 3 → env flag + Developer. **Production planning ke cross-POST list me cancel + reschedule bhi** (sirf move / release / start nahi). products.html me dead JS (`/products/<id>/variants/add` jaise routes jo hain hi nahi) — saaf karna.

### 10.8 Build order me jude steps (section 8 me)
- **P0-2 me:** pip install + requirements pin + `ERP_DEV` / secret-key rules + WAL / busy_timeout.
- **P0-4 ke saath:** **test-login hook** (purane saare test scripts ek logged-in Developer test client se chalein) + registry self-check test (har `url_map` rule ka page key + min level; stale DB key flag).
- **Naya P0-6b: View-only user ko Edit controls aur ~35 cross-module links 403 ke bajaye hide / disable dikhein** (`can('
- **P0-8 me:** deploy tooling update (logged-in health / sweep, public login POST), key rotation, break-glass doc.

### 10.9 Naye scenarios (22 me jode)
23. CSRF: bina token / galat token / multipart upload / purana khula tab. 24. User ke paas **zero permitted page** (kahan land kare?). 25. Ceiling kam hui jab staff roles me wo pages the. 26. `next=` open-redirect + POST URL `next` me. 27. Logout aur `session_version`. 28. Lockout se Admin / Developer ko DoS karne ki koshish. 29. 413 upload handler + anonymous `/static`. 30. Deploy health check guard ke saath pass. 31. Dashboard 30 s reload + expired session. 32. View-only user: Add / Edit / toggle buttons + cross-module links nahi dikhte. 33. Admin ne Developer ka username banana chaha -> generic error. 34. Temp password response cache / flash me nahi.

### 10.10 User se tay karwane wali nayi cheezein (section 9 ke 8 ke saath)
9. **Admin account kaun banaye?** Recommended: **sirf Developer** (Admin kisi aur Admin ko nahi bana sakta).
10. **Tour / demo** live par bilkul band (env flag) — recommended; sirf aap (Developer) local / beta par chalayen.
11. **Approve** (stock adjustment) shuru me Developer / Admin only — theek?
