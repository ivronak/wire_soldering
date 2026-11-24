# ERP me "kaun ne kiya" — User / Person ka use — FLOW (2026-11-24)

Status: **FLOW DRAFT — user ka pehla faisla ho gaya (section 12: "People master nahi, sab Users me"). Section 5 / 6.3 / U3 us se REPLACE hote hain. Baaki faisle section 12.3 me. Code abhi kuch nahi badla.**
Pehle audit: [`user_usage_audit_2026_11_24.md`](user_usage_audit_2026_11_24.md). Ye doc us audit ke baad "pura flow soch ke" likha hai.

---

## 1. Requirement (user, 24 Nov — apne shabdon me)

- "ERP me audit nikal kaha kaha user ka use ho raha hai — user ka dropdown ya user ka naam / by user — **ye user use honge, Developer ke sivay**."
- "Tu khud pehle pura flow soch ki kya hoga, fir hum decide karte hain."

## 2. Sachchi halat (audit se, 1 minute me)

- `users` table sirf login / admin screens / sidebar / audit log me use hoti hai. Business me koi table `users` se juda nahi.
- 10 "kaun ne kiya" columns **free text** hain (operator, inspector, issued_by, received_by, returned_by, written_off_by, recorded_by, reviewed_by, set_by, tested_by).
- Business documents par **created_by / approved_by / cancelled_by hai hi nahi**. Time (`cancelled_at`, `approved_at`, `finalized_at`, `reviewed_at`) kai jagah save hota hai, **kisne** — kahin nahi.

## 3. Spec kya bolta hai (SSOT)

| Spec | Matlab |
|---|---|
| §2.2 rule 10 / §17 | Har critical transaction ka audit trail: **Who**, when, what (create / edit / approve / cancel) |
| §10.10 | Printed document ke footer me **"Created By" / "Approved By"** |
| §1 traceability + §4.7 + §14 | Batch ↔ **Machine / Operator** — operator traceable hona chahiye |
| Line 840 (client) | Aage **operator-wise performance report** (better order → better operator) |
| Line 872 (client) | HR / Accounts isi software me aayenge (matlab aage "employees" ki list chahiye hogi) |

Nateeja: spec 2 alag cheezein maangta hai — (a) **button kisne dabaya** (audit), (b) **kaam kisne kiya** (operator traceability). Yahi flow ki jad hai.

---

## 4. Core idea — "kaun" 2 tarah ka hota hai (inhe kabhi mix nahi karna)

### W1 — **Actor** = jisne ERP me button dabaya (login user)
- **Apne aap** session se aata hai. Type / dropdown **nahi** — jhootha naam daal hi nahi sakte.
- Naye columns: `created_by_id`, `cancelled_by_id`, `approved_by_id` (jahan wo step hai). Sirf id, nullable (purane rows = "—").
- Isi me wo purane text fields aate hain jo asal me actor hain: **`reviewed_by`** (variance review — abhi "Your name" type karna padta hai) aur **`set_by`** (machine extra hours).

### W2 — **Responsible person** = jisne asal kaam kiya (kabhi login wala, kabhi nahi)
- Operator, inspector, lab tester, store wala, production wala, jisne maal liya / lautaya / write-off me zimmedar.
- Ye **chuna** jaata hai (dropdown), type nahi.
- Kyun alag? Supervisor 20 entries karta hai — **entry karne wala (W1)** supervisor hai, par **operator (W2)** Ramesh hai.

| Field | Abhi | Naya class |
|---|---|---|
| `reviewed_by` (variance) | text "Your name" | **W1** automatic |
| `set_by` (machine extra hours) | text | **W1** automatic |
| `issued_by` (store) | text | W2 — default = logged-in person |
| `received_by` (production) | text | W2 |
| `returned_by` | text | W2 |
| `written_off_by` (zimmedar) | text, zaroori | W2 |
| `operator` (routing stage) | text + datalist | W2 |
| `recorded_by` (production output) | text, default = last operator | W2 |
| `inspector` (inward QC) | text, zaroori | W2 |
| `tested_by` (stage lab QC) | text, zaroori | W2 |
| `"Auto-issue"` | system text | **text hi rahega** (koi insaan nahi) |

---

## 5. W2 ki list kahan se aaye — 3 raaste (yahi sabse bada faisla)

Problem: operator / lab wala / store ka banda **ERP login nahi rakhta** ho sakta hai. Sirf login users ki list me wo aayenge hi nahi.

| | Option 1 — sirf login users | **Option 2 — "People" master (meri recommendation)** | Option 3 — text hi rahe |
|---|---|---|---|
| List ka source | `users` (active, Developer nahi) | naya master **People**: naam, type (Office / Floor), mobile (optional), optional login-link, active | wahi purane likhe naam (datalist) |
| Floor worker | har ek ko login dena padega | master me naam add — login nahi chahiye | type |
| Typo / duplicate | nahi | nahi (ek hi record) | **haan** ("Ramesh", "ramesh bhai") |
| Operator-wise report (spec) | sirf login walon ka | ✅ sab ka | ❌ |
| Aage HR | alag banana | ✅ People = HR employees ka beej | ❌ |
| Developer | filter se bahar | **banta hi nahi** (server block) | — |
| Kaam / complexity | kam | **medium** (1 naya page + FK + migration) | ~0 |

**Option 2 kaise kaam karega (simple):**
1. Naya page **Masters → People** (Users page jaisa drawer; page key `people`; Developer-only nahi, Admin ceiling se milta hai).
2. Naya login user banate hi uska **People row apne aap** ban jaata hai (type Office, link = user). User deactivate → person inactive. **Developer ka row kabhi nahi banta.**
3. Floor workers (login nahi) → Admin / jise `people` Edit mile, master me naam jodta hai (naam unique, case-insensitive).
4. Har dropdown = **active People**. Chuna hua: `person_id` (FK) + purana text column **snapshot** (print / purane code ke liye).
5. Dropdown me type karke search (list lambi ho sakti hai), default = logged-in user ka person (jahan ho sake).

---

## 6. Developer ka rule — saaf niyam

1. **Developer kisi dropdown / list me nahi** (People, W2 pickers, koi bhi "user chuno"). Server par bhi reject — crafted POST me Developer ka id bheja to error.
2. **Developer ne koi action kiya** (PO banaya, cancel kiya) → W1 me **asli id save** (audit sach rahe). Dikhaate waqt:
   - non-Developer viewer / **print** → label **"Administrator"** (client ke customer ko "Hardik" nahi dikhna chahiye);
   - Developer khud dekhe → asli naam.
   - Ek hi helper: `actor_label(user, viewer)`.
3. Deactivated user / inactive person: **naye entry me nahi dikhta**, par purane records me naam dikhta rehta hai.
4. Role badalne se picker par asar nahi (picker = sirf active + not Developer). Module-permission ke hisaab se filter **abhi nahi** (baad me chahe to).

---

## 7. Screen-by-screen flow (kya badlega)

Har jagah naye W1 columns = **sirf nullable add** (live DB safe, purana data nahi tootta).

| Module | W1 (automatic) | W2 (dropdown) | Dikhega kahan |
|---|---|---|---|
| Quotation | created, finalized/approved, cancelled | — | list View drawer, **print footer Created By / Approved By** |
| Purchase order / GRN / Purchase invoice / Purchase return | created, cancelled | — | View drawer + print footer |
| **Inward QC** | entered-by (created) | **inspector** | QC view, PO docket |
| Sales invoice / Receipt / Credit note / Dispatch | created, cancelled | — | print footer + list |
| Production order | created, released, cancelled | — | list/view |
| **Material issue** | created, cancelled | **issued_by** (default = me), **received_by** | issue list, print slip (Issued by / Received by names) |
| **Material return / Write-off** | created | **returned_by** / **written_off_by** * | list, print, variance |
| **Routing stage** | started / completed / reopened by | **operator** | routing, dashboard, scrap labels |
| **Stage Lab QC** | entered-by | **tested_by** * | TC print |
| **Production output** | created, cancelled, **reviewed_by (auto)** | **recorded_by** | output list+print, variance |
| Machine extra hours | **set_by (auto)** | — | dashboard |
| Stock transfer / adjustment / opening stock | created, **approved_by** (special permission wala), cancelled | — | list + print |

`*` = abhi zaroori field hai → zaroori hi rahega (dropdown me "Select…" na chhoda ja sake).

**Is flow me nahi aata (alag bada step):** spec §17 ka poora "Old JSON / New JSON" audit trail (har master / transaction edit ka diff). Wo `audit_log` ko business tak failaana hai — alag, bada kaam. Yahan sirf "kaun" columns.

---

## 8. Scenarios (inka auto-test banega)

1. Developer People / kisi picker me **nahi** dikhta. Developer ka id POST karo → reject.
2. Developer PO banata hai → DB me uska id; **Admin** list/print me "Administrator"; Developer apni screen me asli naam.
3. Naya login user banao → People me row apne aap; deactivate → picker se gayab, purana record naam dikhata hai.
4. Store user material issue banata hai → `issued_by` default wahi; `received_by` me floor worker (login nahi) chuna ja sakta hai.
5. Floor worker "Ramesh" operator chuna → routing, dashboard, scrap label, scrap pack label sab me "Ramesh".
6. Purane rows (created_by NULL, text-only operator) list / print / variance me **"—" / purana text**, crash nahi.
7. View-only user naam dekh sakta hai, badal nahi sakta (guard).
8. Supervisor entry karta hai: W1 = supervisor (auto), W2 operator = Ramesh — dono alag save.
9. Person rename → purane docs me snapshot text (B); actor (W1) me current naam.
10. Duplicate People naam (case alag) → error. Do asli Ramesh → alag naam ("Ramesh P").
11. Crafted POST: inactive person / dusre type ka id → reject.
12. `reviewed_by` ab type nahi hota; review karne wale login user ka naam auto.
13. `"Auto-issue"` flow (routing me use hota hai) **toot-ta nahi** (text check waisa hi).
14. Tour / demo (Gujarati) chalta rahe (demo operator / lab ab People se).
15. Role badalna / user ka role badalna picker ko nahi chhedta.

---

## 9. Is flow me khud ki kamiyaan / risk (critic)

1. **Scope bada** — ~10 screens + prints + dashboard JS (form string se banta hai) + tour + variance. Isliye ek saath nahi, module-by-module.
2. **Floor block hone ka khatra** — zaroori text fields (inspector, tested_by, written_off_by, operator) dropdown banne par agar People khaali hui to kaam ruk jaayega. **Live se pehle People bharna (deploy checklist)** ya rollout me "Other (type name)" fallback — section 10, faisla 4.
3. **Purana text kaise jude** — "Ramesh" / "ramesh bhai" auto-match galat ho sakta hai. Isliye purane rows **text hi rahenge** (nayi entry se link).
4. **Do list ka jhanjhat** (Users + People) — auto-link se kam hota hai, par Admin ko samajhna padega: "login chahiye to User banao, sirf kaam ka naam chahiye to People".
5. **Phase 0 abhi live nahi** — ye kaam Phase 0 ke `users` table par tikta hai, isliye deploy saath ya Phase 0 ke baad.
6. **Print par naam** — customer ke document par kisi ka naam jaana privacy-sensitive; footer "Created By" ko company setting se on/off karna chahe to baad me (abhi default on, spec §10.10).
7. **Name collision** (do asli Ramesh) — sirf unique naam rakhne se hal; employee code abhi nahi (HR aane par).

---

## 10. User se tay karne wali cheezein (har ek ke saath meri recommendation)

| # | Sawal | Meri recommendation |
|---|---|---|
| 1 | W2 ke picker kahan se? Option 1 / **2** / 3 | **Option 2 (People master)** — spec ka operator-wise report + aage HR |
| 2 | Developer ne action kiya to dusron ko kya dikhe? | **"Administrator"** (asli id audit me safe) |
| 3 | Kin documents par created / approved / cancelled by? | **Saare transactions** (masters baad me), print footer on |
| 4 | Rollout me "Other (type name)" fallback? | **Nahi** — live se pehle People bharo (checklist), warna data phir ganda |
| 5 | `reviewed_by`, `set_by` auto (type band)? | **Haan** — wo asal me actor hain |
| 6 | Purane text rows? | **Jaise hain rahen** (text), nayi entry se link |
| 7 | Picker module-permission se filter ho? | **Abhi nahi** (har active person) |
| 8 | Business-wide Old/New JSON audit (spec §17) | **Alag baad ka step** |

## 11. Build order (faisle ke baad; har step: auto-test + tracker)

- **U1** — helper layer (no UI): `actor_label`, Developer-exclusion, tests.
- **U2** — W1 columns + auto-capture, **ek module ek time** (pehle Manufacturing: material issue → routing → output; phir Procurement, Sales, Inventory) + View / print footer.
- **U3** — People master (page, drawer, registry key, permission, auto-link user, Developer block).
- **U4** — W2 fields ko dropdown: Routing operator (+ dashboard) → Material issue/return/write-off → Production output + variance → Inward QC + Lab QC.
- **U5** — safai (datalists, tour), tracker / memory, deploy checklist (People pehle bharo).

---

## 12. USER KA FAISLA (24 Nov 2026) — **ye section upar ke section 5 / 6.3 / 7 (U3) / 10 #1 se upar maana jaayega**

### 12.1 Faisla (user ke shabdon me)
"Naya People master nahi banate. **User me hi sab banayenge** — role dekar jo unhe dena ho. Floor worker ko login pass dena ya nahi dena wo unki problem hai, par sab user wahin Users me banenge. Isse cheezein aasan ho jaayengi."

→ **Option 2 (People master) reject.** Ek hi list: **Users**. Floor worker, store wala, lab wala, operator, Admin — sab Users me, **Role** se pehchaan.

### 12.2 Isse flow kaise badla (maine dobara soch ke)

1. **Picker = Users table se** (W2 ke saare dropdown): `is_active` + role `system_key != developer`. Developer rule waisa hi (section 6 ke 1, 2, 3 jaisa); "People auto-link" ka kaam khatam.
2. **Chuna hua** = `<field>_user_id` (FK users.id) + purana text column **snapshot** (print / purana code ke liye). Actor (W1) waisa hi — sirf `*_by_id`.
3. **"Role dekar aasan"** ka matlab: role se pata chale ki banda kya hai. Do tareeke the:
   - (a) picker role ke **page-access** se filter ho (jaise operator picker me sirf wo jinke role me Routing ho). **Kamzor**: floor worker ko sirf dropdown me aane ke liye rights dene padenge; `received_by`, `returned_by`, `written_off_by` kis page se bandhein — saaf nahi; rights badle to dropdown chupke badal jaata hai.
   - (b) **Meri recommendation:** picker me **saare active users**, har naam ke saath **role dikhe** ("Ramesh — Operator"), type karke search, role ke hisaab se group. Rights se koi jod-tod nahi. Role = sirf pehchaan + login ke rights.
4. **Floor worker ke roles:** Admin khud banata hai — jaise "Operator", "Lab", "Store". Jis worker ko login nahi dena, uske role me **koi page nahi** (ya sirf Dashboard) — ye pehle se allowed hai (role bina pages ke ban sakta hai).
5. **Users page ko 2 chhote badlav chahiye** (neeche 12.3 ke sawal 2 / 3): role se filter, aur "login nahi" waale users ka saaf case.
6. Purane text rows jaise hain; nayi entry se `user_id` judega. `"Auto-issue"` text hi rahega.
7. Scenarios (section 8) me badlav: #3 ("People row apne aap") hata; #5, #10, #11 me "People" ki jagah "User" padho (duplicate = same mobile already unique hai); naya #16: **floor worker user bina login ke** operator ban sake; #17: us user ka password kisi ko nahi diya → login par sirf generic error, picker me phir bhi dikhe.

### 12.3 Is faisle ke baad **naye / bache hue sawal** (har ek ke saath meri recommendation)

| # | Sawal | Kyun ab zaroori hua | Recommendation |
|---|---|---|---|
| A | **Picker me kaun dikhe**: (a) role ke page-access se filter, ya (b) saare active users + role label + search | list ab mixed hai (Admin, accountant, operator) | **(b)** |
| B | **Mobile number zaroori rahe?** Abhi login ID = mobile, har user ke liye zaroori + unique. Floor worker ke paas phone na ho to? | worker ko Users me banane ke liye ek asli, alag number chahiye — warna log jhooTha number bharenge | **Mobile optional** tab jab "login allowed" band ho; login allowed ho to zaroori |
| C | **"Login allowed" on/off switch** Users form me. Off = password nahi banta, login nahi chalta, par picker me aata hai | Bina switch ke har worker ka account asli active password ke saath (temp password ban hi jaata hai) — aur agar role me rights hon to kisi ko password pata chale to kaam ho sakta hai | **Haan, switch lagao** (chhota kaam; aapki "login de ya na de" wali baat ko seedha support karta hai) |
| D | Users list me **Role filter** (chips / dropdown) | 50+ users hone par role se dhundna aasan | **Haan** |
| E | baaki section 10 ke #2–#8 | jaise the | wahi recommendation |

### 12.4 Naya build order (U3 badla)
- **U1** helper layer (`actor_label`, Developer exclusion, `pickable_users()`) — no UI
- **U2** W1 columns + auto-capture, module-by-module (Manufacturing pehle)
- **U3 (naya)** Users page: **Login allowed switch + optional mobile** (agar B, C haan) + Role filter (D) — sirf Users screen + auth login check; naya master / page nahi
- **U4** W2 fields ko dropdown (Routing operator + dashboard → Material issue/return/write-off → Production output + variance → Inward QC + Lab QC); default = logged-in user
- **U5** safai (datalists, tour), tracker / memory, deploy checklist: **live se pehle floor workers ko Users me banao**

### 12.5 User ke jawab (24 Nov) — sawal B, C — **ye 12.3 / 12.4 se upar**
User: "Abhi jaisa hai waise hi rehne de. Admin ko login dena hoga to user ko password dega, warna nahi dega."

- **C — "Login allowed" switch: NAHI.** Users screen / login me **koi badlav nahi**. Har naya user pehle jaisa banta hai (temp password ek baar dikhta hai). Admin chahe to worker ko password de, chahe to na de.
- **B — Mobile: jaisa hai waisa** (zaroori + unique). Floor worker ke liye bhi ek asli number chahiye.
- **A (picker)** aur **D (Role filter)** par user ne alag se kuch nahi bola; "jaisa hai waisa" ke hisaab se **minimal** rakha: **A = (b)** saare active users + role label + search; **D = abhi nahi** (Users list me search pehle se hai, zarurat padi to baad me). Jab tak user na badle, yahi maana jaayega.
- Nateeja: **U3 (Users page badlav) poora hat gaya.** Build order ab: **U1 → U2 → U4 → U5**.
- Risk jo user ne jaan-boojh ke chhoda: password-wale active worker accounts (agar role me rights hon aur password pata chal jaye). Mitigation sirf process: worker ke role me kam se kam pages; password na dena ho to credentials page par baat khatam.

### 12.6 D (Role filter) — user ne haan kaha, **BAN GAYA** (24 Nov)
Users list ke toolbar me "Role" dropdown (`?role=<id>`), ginti ke saath, search + status ke saath chalta hai; Admin ko Developer role option nahi dikhta. Test 9/9. Build order ab: **U1 → U2 → U4 → U5** (U3 = sirf ye filter tha, ho gaya).
