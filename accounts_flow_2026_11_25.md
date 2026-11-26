# Accounts module — flow (25 Nov 2026) — DRAFT, user approval ke baad hi build

**Status:** sirf flow likha hai. Kuch build / migrate nahi hua. Spec: `Manufacturing_ERP_Unified_Requirements_Specification.md` §23 Phase 7 (Tally-grade double-entry, bill-by-bill), Phase 8 (reports, GST), Phase 9 (expenses), Phase 10 (dashboards).
Rule (CLAUDE.md §5): **har financial transaction balanced Dr/Cr ke saath; koi hard delete nahi (cancel = reverse entry); permission backend pe.**

---

## 1. Abhi kya hai (code se dekha)
| Cheez | Sthiti |
|---|---|
| `ChartOfAccountsGroup` (name, classification) | Sirf 2 group auto bante hain: "Sundry Debtors" (ASSET), "Sundry Creditors" (LIABILITY). Koi seeded chart nahi. |
| `Ledger` (name, group, opening + type, `current_balance`, gstin) | Sirf Customer / Vendor banate waqt auto banta hai. **Sign rule: Cr = plus, Dr = minus.** |
| Posting | Har module seedha `ledger.current_balance += / -=` karta hai: sales invoice (`billing.py`), receipt (`collect.py`), sales return, purchase invoice + return (`posting.py`). **Ek taraf ka running balance — Dr/Cr jodi nahi, journal nahi.** |
| Vendor ko payment | **Hai hi nahi** (vendor ka balance kabhi kam nahi hota). |
| Cash / Bank ledger, Expenses, GST ledgers, Sales / Purchase / Stock account | **Nahi hain.** |
| GST | Invoice / bill par `tax_type` (intra / inter) + `tax_total` hai; CGST / SGST / IGST ka alag amount store nahi; line par `tax_rate`. |
| Reports | Customer statement, Aging (receivables). Payables aging, Trial Balance, P&L, Balance Sheet nahi. |

**Matlab:** Accounts ka asli kaam = ek **journal (voucher + entries) layer** banana jo in sab ko Dr/Cr me likhe, aur `current_balance` ko usse **calculate** kare (khud store ka source nahi).

---

## 2. Core idea (3 cheezein, mix mat karna)
1. **Voucher** = ek accounting event (Sales, Receipt, Payment, Purchase, Journal, Contra, Debit/Credit note). Header: no., date, type, narration, source document, status (Posted / Cancelled), created_by.
2. **Entry (line)** = voucher ki ek Dr ya Cr line: ledger, amount, Dr/Cr. **Sum(Dr) = Sum(Cr) har voucher me** — server save se pehle check karta hai, warna reject.
3. **Ledger balance** = opening + sum(entries). `current_balance` ab cache hai jo entries se banta hai, koi module ise seedha nahi badlega.

**Cancel:** voucher delete nahi; **reverse voucher** (ulti entries) banta hai, dono dikhte hain, audit saaf.
**Period lock:** FY close ke baad purani date me entry nahi (Phase 8, abhi sirf field rakhenge).

---

## 3. Chart of accounts (starter, Admin badal sakta hai)
Groups (Tally jaise): Capital, Reserves, Loans, **Current Liabilities** (Sundry Creditors, GST Payable, TDS/TCS Payable), **Current Assets** (Sundry Debtors, Cash, Bank, Stock-in-hand, GST Input, Advances), **Sales Accounts**, **Purchase Accounts**, **Direct Expenses**, **Indirect Expenses**, Fixed Assets.
Pehle se bane (system ledgers, edit / delete nahi): Sales, Purchase, Sales Return, Purchase Return, Cash, Output CGST / SGST / IGST, Input CGST / SGST / IGST, Freight / Other charges, Round-off, Stock-in-hand, COGS (Cost of goods sold), Scrap sales.
**Bank:** har Payment Mode ya "Bank account" master ko ek ledger se jodna (neeche sawal #3).

---

## 4. Auto-posting (purane screens se, bina naye typing ke)
| Event | Dr | Cr |
|---|---|---|
| Sales invoice Posted | Customer (total) | Sales (subtotal), Charges, Output GST (CGST+SGST ya IGST), Round-off |
| + COGS | COGS (cost_total) | Stock-in-hand |
| Receipt | Cash / Bank (payment mode se) | Customer |
| Sales return / credit note | Sales Return + Output GST | Customer; + COGS ulta (stock wapas) |
| Purchase invoice Posted | Purchase / Stock-in-hand (subtotal), Input GST, Charges | Vendor (total) |
| Purchase return | Vendor | Purchase Return + Input GST |
| Vendor payment (**naya screen**) | Vendor | Cash / Bank |
| Expense (**naya**, Phase 9) | Expense ledger + Input GST | Cash / Bank / Vendor |
| Journal / Contra (manual) | user chunta hai | user chunta hai |

Har posting **ek hi jagah** (`app/accounts/posting.py`) — jaise `purchase_invoices/posting.py` ka pattern. Purane `current_balance += x` wale lines hatenge, wahan se voucher banega.

---

## 5. Screens
1. **Chart of accounts** (groups + ledgers, tree; system ledgers locked) — Masters me.
2. **Vouchers** list (type / date filter) + **View** drawer (Dr/Cr lines + source doc link).
3. **Manual voucher** entry: Payment, Receipt (advance / on account), Journal, Contra; **balance indicator** (Dr = Cr tak Save band).
4. **Ledger statement** (kisi bhi ledger ka: opening, entries, closing; drill-down voucher / source).
5. **Outstanding**: Receivables aging (hai) + **Payables aging** (naya), bill-by-bill knock-off.
6. **Reports (Phase 8):** Day book, Cash book, Bank book, **Trial Balance**, **P&L**, **Balance Sheet**, GST summary.
Sab pages ki role keys alag (`accounts_*`), cost / profit wali pages ki tarah View / Edit; "who did it" (`created_by_id`, `cancelled_by_id`) har voucher par.

---

## 6. Bill-by-bill (Phase 7)
Receipt ab already invoice se allocate hota hai (`ReceiptAllocation`); wahi pattern Payment ke liye (vendor ke bills). Options: **Against bill / On account (advance)**. Aging = bill ki due date se (0-30, 31-60, 61-90, 90+).

---

## 7. Migration / purana data (sabse risky hissa)
- Naye tables: `vouchers`, `voucher_entries` (+ chart seed, system ledgers, FY / lock field). Add-only.
- **Backfill:** live par pehle se invoices / receipts / bills hain. Unke liye **opening-balance style voucher** banana: party ledgers ka maujooda `current_balance` ek "Opening balance" journal me jaata hai (date = go-live date). Purane documents ko dobara post **nahi** karenge (double count ho jayega).
- Backfill ke baad check: **har party ledger ka naya balance = purana `current_balance`** (jaise aging me already hai).
- Pehle DB copy / live snapshot par dry-run (jaisa Phase 0).

---

## 8. Build order (har step: auto-test + tracker; live deploy sirf user ke "haan" par)
- **A1** Chart of accounts + system ledgers + `vouchers` / `voucher_entries` + balance-check helper. Koi purana flow nahi chhuta.
- **A2** Backfill + ledger balance entries se calculate (customer / vendor), purane balance se tally.
- **A3** Auto-posting: Receipt, Sales invoice (+COGS), Sales return.
- **A4** Auto-posting: Purchase invoice, Purchase return.
- **A5** Vendor payment screen + payables aging.
- **A6** Manual vouchers (Payment / Receipt / Journal / Contra) + ledger statement.
- **A7** Reports: Day / Cash / Bank book, Trial Balance, P&L, Balance Sheet.
- Baad me: GST reports, TDS / TCS, expenses + fixed assets, March Baki (Phase 8 / 9).

---

## 9. Risk / kamiyaan (khud critic)
1. **Rounding:** Float se Dr ≠ Cr paisa-do-paisa. Voucher me amounts 2 decimal round karke compare; Round-off ledger me farak.
2. **Cost (COGS) abhi lot-wise approx hai** (FIFO / WAVG baaki, tracker Phase 3). COGS entry usi cost se banegi; jab stock cost true-up aayega tab entries badalna padega.
3. **CGST / SGST / IGST ka alag amount store nahi.** Posting me `tax_type` + `tax_total` se half-half ya poora IGST bana denge; line-wise rate alag ho to line se jodna padega.
4. **Purane docs purane GST rules par** (`gst_on_charges` flag) — backfill me unka total waisa hi.
5. **Do jagah balance** (purana `current_balance` + naye entries) ka drift: isliye A2 me balance sirf entries se; purane `+=` lines hatenge, ek hi source.
6. Tally-style keyboard shortcuts (F4-F9) — CLAUDE.md me "vanilla JS minimal"; shuru me normal form, shortcuts baad me.
7. **Opening balances customer / vendor form me hi hain** — ab voucher se aayenge; form me edit hone par entry adjust (ya lock after first posting).

---

## 10. User se tay karne wali baatein (har ek ke saath meri recommendation)
1. **Scope abhi:** Phase 7 + reports (A1–A7). GST returns (GSTR-1/3B), TDS/TCS, fixed assets baad me. → **Haan, yahi.**
2. **Backfill:** purane docs ko dobara post nahi, sirf opening journal. → **Haan.**
3. **Bank:** har Payment Mode ke saath ek ledger (Cash / UPI / Bank) auto-bane, ya alag "Bank account" master. → **Payment mode ke saath ledger jodna** (chhota, kaam chal jata hai); bank reconciliation baad me.
4. **Stock / COGS:** perpetual (har invoice par COGS) ya sirf period-end closing stock. → **Perpetual** (cost_total pehle se invoice par hai).
5. **Vendor payment:** naya screen (Payment) A5 me, bill-by-bill. → **Haan.**
6. **Financial year:** April–March, period lock field abhi rakhein, wizard (March Baki) baad me. → **Haan.**
7. **Role keys:** `accounts` (vouchers, ledgers) aur `accounts_reports` alag (profit jaisi sensitive). → **Alag.**

---

## 11. USER KA FAISLA (25 Nov) + BUILD STATUS
User: **"sab haan, A1 shuru karo"** — section 10 ke saare 7 sawalon par meri recommendations maani gayi.
- **A1 BAN GAYA (25 Nov):** migration `f8c2d5a1e9b6`, chart + 18 system ledgers, `vouchers` / `voucher_entries`, `app/accounts/posting.py`, Accounts module + Chart of accounts page (read-only). Test a1 31/31; purane suite 169/169. Koi purana flow nahi badla.
- **Note:** naye page ko Admin / staff tak pahunchane ke liye Developer ko Admin access me 'Chart of accounts' tick karna padega (ceiling rule).
- **Agla: A2** — backfill (purane party balances ka opening journal) + ledger balance entries se.
- **A2 BAN GAYA (25 Nov):** opening voucher helper + `accounts-backfill` / `accounts-tally` CLI + Customer / Vendor opening hooks; backfill difference-based (idempotent). Test 20/20 + live snapshot 9/9. Live deploy A2-A4 ke saath hi (deploy script me `flask accounts-backfill` jodna hai, `inventory-backfill` ke baad). Agla: **A3**.
- **A3 BAN GAYA (25 Nov):** migration `a9d4e1c7b3f2` (payment_modes.ledger_id) + `app/accounts/autopost.py`; Receipt, Sales invoice (+COGS ek hi voucher, GST CGST/SGST ya IGST, round-off), Sales return (Credit note + COGS ulta) auto voucher; cancel = reversal voucher. Test 31/31, tally 0. Live deploy A2-A4 ke saath. Agla: **A4** (Purchase invoice / return).
- **A4 BAN GAYA (25 Nov):** Purchase bill (Dr Stock-in-hand + Input GST, Cr Vendor) aur Purchase return (Debit note) auto voucher; cancel = reversal. Test 45/45, tally 0. Open point: production stock movement (RM -> WIP -> FG) ka voucher abhi nahi — A7 se pehle decide. Agla: **A5**.
- **A5 BAN GAYA (25 Nov):** migration `b5e2f8a1d4c6` (vendor_payments + allocations); Vendor payments screen (bill-by-bill + On account) + Payment voucher + cancel; Payables aging page. Test 61/61, tally 0. Limit: on-account advance ko baad me bill se jodna A6 me. Agla: **A6**.
- **A6 BAN GAYA (25 Nov):** manual vouchers (Payment / Receipt / Journal / Contra) + Vouchers list / View / reverse + Ledger statement + vendor advance apply. Party ledger line par current_balance sync. Test 95/95. Agla: **A7** (reports; Stock-in-hand / production vouchers ka sawal A7 se pehle).
- **A7 BAN GAYA (25 Nov):** Reports (key accounts_reports): Day book, Cash / Bank book, Trial balance, P&L, Balance sheet — sab voucher entries se. Test 123/123, live-snapshot dry-run OK. **A1-A7 poore.** Baaki (flow doc ke "baad me"): GST reports (GSTR-1 / 3B), TDS / TCS, expenses + fixed assets, production vouchers (Stock-in-hand ko sahi karne ke liye), March Baki (period lock), live deploy.
