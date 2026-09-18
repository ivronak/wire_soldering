# learning.md — MOST IMPORTANT (Manual Flask Learning Mode)

> **Priority #1 for every AI agent (Claude / Cursor / anyone).**  
> Agar session limit khatam ho jaye, naya agent **pehle yeh file + `tracker.md` → Current Focus** padhe, phir aage badhe.  
> **Date locked:** 2026-09-17 — user ne explicitly decide kiya.

---

## Goal (ek line)

User **khud** Flask backend type karega. AI **sirf sikhayega** (kyun + kya + chhota snippet).  
End goal: AI / dost / Laravel ke bina bhi error padh ke fix kar sake.

---

## Kya BADAL gaya (purane plan se)

| Pehle | Ab |
|---|---|
| AI mockups / backend files khud likh deta tha | **Backend (Part 2): user type karta hai**, AI guide karta hai |
| Bade chunks me code dump | **Ek micro-step = ek chhoti cheez** (1 file / 1 function / 1 concept) |
| "Kaam ho gaya" = files exist | "Kaam ho gaya" = **user samajh ke khud chala sakta hai** |

Mockups (Part 1) pehle jaisi rah sakti hain — already mostly ban chuki hain.  
**Naya rule Part 2 (Flask/SQLAlchemy) pe apply hota hai.**

---

## Teaching Loop (har micro-step — yehi rhythm)

```
1. CONCEPT   — 2–5 lines Hinglish: yeh kya hai, kyun chahiye (code se PEHLE)
2. WHERE     — kaunsi file / folder (path batao)
3. TYPE THIS — chhota snippet (ideal 5–25 lines). User KHUD type kare.
4. RUN       — exact terminal command (Windows PowerShell friendly)
5. CHECK     — kya dikhna chahiye (browser / terminal output)
6. IF STUCK  — error ka matlab pehle explain, phir hint; poora file rewrite mat karo
7. TICK      — tracker.md me micro-step tick + Current Focus update
```

**Speed vs learning balance:**
- Zyada chhote steps = zyada confident, thoda slow — **OK, yeh intentional hai.**
- Speed badhane ka tareeka: har module ke baad "pattern repeat" — Machine Master pe Unit jaisa, kam concept / zyada practice.
- Kabhi bhi "main poora module ek baar me likh deta hoon, tum padh lena" mat karo — **violate**.

---

## Agent ko kya KARNA hai / kya NAHI

### KARNA
- Har step se pehle: *"Is step me tum X likhoge, kyunki Y."*
- Snippet + file path + run command do.
- User ke paste/type ke baad verify help (diff / "yeh line missing hai").
- Hinglish comments suggest karo jo user type kare.
- Error aaye to **pehle meaning**, phir fix direction.
- Session end pe: `tracker.md` Current Focus = **aglai exact micro-step**.

### NAHI KARNA
- Part 2 me bina user ke poori `routes.py` / `models.py` khud mat likh do (unless user explicitly bole "tum likh do, main baad me padhunga").
- Ek message me 5 files / 200 lines mat dump karo.
- Stack mat badlo (Flask + Jinja + SQLite + SQLAlchemy + Tailwind CDN + vanilla JS).
- "Black box" shortcuts (copy-paste magic) mat do bina explain ke.

**Exception:** Agar user clearly bole *"ab tum likh do speed ke liye"* — tab OK, lekin pehle confirm + phir bhi short explain.

---

## Part 2 order (module by module — pehle Unit Master)

Same order as masters (simplest → harder):

1. **Foundation once** (sirf pehli baar): `run.py`, `app/__init__.py`, `extensions.py`, empty `models.py`, `requirements.txt`, venv  
2. **Unit Master** — Step B → C → D (teach + user types)  
3. Machine Master (pattern repeat — kam naya concept)  
4. Vendor → Customer (richer forms, soft-delete, later auto-ledger)  
5. Raw Material (FK to Unit + Category)  
6. Product (+ variants later if needed)  
7. Warehouse, RM Category, Product Category  

Har module ke andar micro-steps `tracker.md` me tick honge.

---

## Unit Master — pehla backend path (example micro-steps)

Jab Part 2 start ho, **Current Focus** inme se ek hoga:

| # | Micro-step | User kya type karega | Check |
|---|---|---|---|
| F1 | venv + `pip install flask` | terminal | `python -c "import flask"` |
| F2 | `run.py` + minimal app | 2 chhote files | browser `127.0.0.1:5000` hello |
| F3 | Blueprint / `units` route, fake list | `routes.py` + template shell | `/units` page |
| F4 | Jinja: mockup → template (still fake data) | copy structure, loops | Unit Master look |
| F5 | SQLAlchemy `Unit` model + DB create | `models.py` | `erp.db` bani |
| F6 | List from DB | route change | table real rows |
| F7 | Add form POST | route + form | naya unit save |
| F8 | Soft toggle `is_active` | toggle route | no hard delete |

**Ek time pe sirf ek row (#) — agla tab jab user bole "ho gaya / samajh gaya".**

---

## Session handoff (limit / naya chat)

Naya agent / Cursor session start:

1. Padho: **`learning.md`** (yeh file)  
2. Padho: **`tracker.md` → Current Focus** (exact micro-step ID, e.g. `Part2 / Unit / F3`)  
3. Padho: **`memory.md`** → Decision: Manual Learning Mode  
4. User se mat poocho "workflow kya hai?" — already locked  
5. Seedha us micro-step ka CONCEPT + TYPE THIS do  

---

## Related files

| File | Role |
|---|---|
| `CLAUDE.md` §0A | Short hard rule (always load) |
| `.cursor/rules/manual-learning.mdc` | Cursor alwaysApply |
| `development.md` §4 / Part 2 | Backend template — ab teach-then-type |
| `tracker.md` | Live: kaunsa micro-step abhi |
| `memory.md` | Kyun yeh mode choose kiya |
