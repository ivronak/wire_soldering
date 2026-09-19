# CLAUDE.md — Project Rules for Claude Code

Yeh file Manufacturing ERP (Wire Soldering business) project ke liye Claude Code ke rules define karti hai. Har naye session ki shuruaat me yeh file automatically load hoti hai — isliye yahan likhe rules hamesha follow karne hain, dobara poochne ki zaroorat nahi.

---

## 0A. ⭐ MOST IMPORTANT — Manual Learning Mode (2026-09-17)

> **Poora playbook:** `learning.md` — agar session limit / naya agent ho toh **pehle wahi + `tracker.md` Current Focus** padho.

**Kya decide hua:** Part 2 (Flask backend) me **user khud code type karega**. AI (Claude / Cursor) **sikhayega** — concept, file path, chhota snippet, run command, check.  
**Kyun:** Future me AI na ho toh bhi user error padh ke fix kar sake. Dost/Laravel pe depend nahi.

**Har backend micro-step ka loop:**
1. CONCEPT (Hinglish, code se pehle) → 2. WHERE (file) → 3. TYPE THIS (chhota) → 4. RUN → 5. CHECK → 6. tracker tick

**Mana hai (default):** Part 2 me AI poori `routes.py` / module khud mat likh de — user type kare. Exception: user clearly bole "tum likh do".

**Flask + HTML (2026-09-19):** Jab feature me route + template dono lagen, **dono sikhao** — HTML chupke mat badlo. CONCEPT me: Flask kya + HTML me kahan kya. TYPE THIS me Python **aur** related Jinja snippet.

**Handoff:** Current Focus me hamesha exact micro-step ID likho (jaise `Part2 / Foundation / F2` ya `Part2 / Unit / F5`) taaki limit ke baad bhi continue ho sake.

---

## 0. Sabse Pehle Yeh Karo (Every Session)

Kaam shuru karne se pehle:
1. **`learning.md`** padho (agar Part 2 / backend / teaching chal raha ho — Priority #1).
2. **`tracker.md`** padho — "Current Focus" section batayega abhi kaunsa module/step / micro-step chal raha hai.
3. **`memory.md`** padho (ya relevant section) — agar koi related decision pehle liya gaya hai, usko dobara mat poocho, usi ke hisaab se aage badho.
4. Agar user ka message kisi purani decision se conflict kare, toh silently follow mat karo — pehle point out karo ki "pehle yeh decide hua tha X, ab aap Y keh rahe ho, confirm karo."

---

## 1. User Profile (Yeh Hamesha Yaad Rakhna)

- User **professional developer nahi hai**. Sirf Flask (Python) thoda-bahut aata hai. React, Laravel, HTML/CSS/JS properly nahi aata.
- User **seekhte hue** project bana raha hai — goal sirf "kaam ho jaaye" nahi hai, goal hai ki user khud samjhe aur future me AI agent ke bina bhi maintain/debug kar sake.
- Isliye:
  - Kabhi bhi "black box" code mat do — hamesha explain karo.
  - Complex jargon avoid karo ya turant explain karo jab use karna zaroori ho.
  - Patience rakho — chhote steps me kaam karo, bade jump mat lo.

---

## 2. Tech Stack (Fixed — Bina Discussion Ke Mat Badlo)

| Layer | Choice |
|---|---|
| Backend | Flask (Python) |
| Templates | Jinja2 |
| Styling | Tailwind CSS (CDN link, no build step) |
| Database | SQLite (`instance/erp.db`) — future me PostgreSQL migrate ho sakta hai jab multi-user scale aaye |
| DB Layer | SQLAlchemy |
| JavaScript | Sirf vanilla JS, minimal (jaise Enter-key navigation) — koi React/Vue/build tooling nahi |

Agar kabhi lage ki is stack se koi cheez achieve nahi ho rahi (e.g. real-time updates, complex client-side interactivity), toh **pehle user se discuss karo**, khud se stack mat badlo. Reasoning `memory.md` → "Decision: Tech Stack" me hai.

---

## 3. Development Workflow (Har Module Isi Pattern Me)

Poora detail `development.md` + Part 2 teaching = `learning.md`. Summary:

```
STEP A: Mock frontend — static HTML, fake data
        → (Part 1) mockups mostly ban chuke / approve flow pehle jaisa

STEP B–D (Part 2 — MANUAL LEARNING MODE ⭐):
        → AI concept + chhota snippet sikhata hai
        → USER khud Flask/Jinja/SQLAlchemy type karta hai
        → Ek micro-step at a time — learning.md ka Teaching Loop
```

**Rules:**
- Ek time pe ek hi module — sab module saath me shuru mat karo.
- Step A ko approve kiye bina Step B shuru mat karo.
- Part 2 me **default: user types, AI teaches** — poora backend AI se mat generate karo (dekho §0A).
- Har naye module/step ke **shuru me**, user ko simple/aasan bhasha (Hinglish) me batao: *"Is step me hum kya banayenge aur kyun"* — assume mat karo ki user ko pata hai.
- Koi bhi step / micro-step complete hone par **`tracker.md` update karo** (checkbox tick, Current Focus badlo, Work Log me entry).
- Koi naya bada decision lene par **`memory.md` update karo** (Key Decisions section me, date + kya + kyun).

---

## 4. Code Style Rules

- **Comments Hinglish me likho** (Roman script, Hindi-English mix) — especially jahan "why" non-obvious ho. Sirf "what" wala English comment kaafi nahi hai.
  - Example: `# Yahan hum hard-delete nahi kar rahe, sirf is_active = False kar rahe hain — kyunki business/financial data kabhi permanently delete nahi hota (audit trail ke liye)`
- **Lekin actual UI/product text HAMESHA English me** (buttons, labels, tooltips, error messages, empty-state text, alert() popups) — Hinglish sirf comments (`<!-- -->`, `//`, `/* */`, Python `#`) ke andar, jo end-user ko kabhi dikhte hi nahi. (Rule clarify hui 2026-09-16 — pehli baar Vendor Master ke View panel me galti se UI text bhi Hinglish likh diya tha, user ne turant point out kiya.)
- Code **simple aur readable** rakho — clever/compressed one-liners avoid karo, kyunki user ko khud padhna/edit karna hai.
- Har naya Python file/function ke upar 1-2 line comment: "yeh file/function kya karti hai, kaunse doosre file/table se juda hai."
- Koi bhi naming convention follow karo consistently (snake_case Python me, folder names lowercase) — `development.md` ke folder structure se match karo.

---

## 5. Core Product Rules (Requirements Doc Se — Kabhi Violate Mat Karna)

Poori detail `Manufacturing_ERP_Unified_Requirements_Specification.md` me hai, especially Section 2.2. Sabse important:

1. **No hardcoded units/materials/products/attributes** — sab dropdown database se aana chahiye, code me fixed list nahi.
2. **No hard delete on business data** — sirf soft-delete (`is_active = False`) ya cancel/reverse mechanism.
3. **Double-entry accounting** (jab Phase 7 aayega) — har financial transaction balanced Dr/Cr ke saath.
4. Backend pe hi permission/validation enforce karo, sirf frontend button hide karna security nahi hai.

---

## 6. Jab Bhi Confusion Ho

- Agar requirement clear na ho, ya do documents (requirements spec vs development.md vs tracker) me conflict dikhe — **pehle user se pooch lo**, guess mat karo.
- Agar koi error aaye jo user khud solve karna chahta hai — sirf fix mat karo, **error ka matlab bhi explain karo** taaki agli baar user khud pehchaan sake.

---

## 7. Project Files Reference

| File | Purpose |
|---|---|
| `Manufacturing_ERP_Unified_Requirements_Specification.md` | Poora product requirement (SSOT) — kya banana hai |
| `learning.md` | ⭐ Manual Flask learning playbook — Part 2 kaise sikhana/type karna hai |
| `development.md` | Phase 1 ka step-by-step execution plan — kaise banana hai |
| `tracker.md` | Live progress — abhi kahan hain (Current Focus = next micro-step) |
| `memory.md` | Decisions aur unke reasons — kyun aisa kiya |
| `CLAUDE.md` | Yeh file — Claude ke liye rules |
| `.cursor/rules/manual-learning.mdc` | Cursor always-on rule — same learning mode |
