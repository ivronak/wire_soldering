# Dashboard plan v2 — 26 Nov 2026

**Kyun v2:** v1 sirf number wale cards tha; user: "dashboard jaisa lag hi nahi raha". Dashboard ko 3 sawaal jaldi batane hain: **kaisa chal raha hai (trend), paisa kahan hai, aaj kya karna hai**.

`/dashboard` = Overview, `/dashboard?tab=board` = live machine board (waisa hi).

## Layout (upar se neeche)

| Row | Panel | Kya batata hai | Permission (View) |
|---|---|---|---|
| Filter | This month / 7 days / 6 months / This year | neeche ke saare "is period" wale panel | - |
| 1 | KPI: Net sales, Collections, Purchases, Net profit | total + pichhle period se % + chhoti trend line | invoices / receipts / purchase_invoices / accounts_reports |
| 2 | Chart: Sales vs Collections vs Purchases | time ke saath (din / hafta / mahina) | wahi |
| 2 | Needs attention | late order, overdue paisa, approval, QC, machine, stock | har line apni permission |
| 3 | Cash and bank | har khate ka balance | accounts_reports |
| 3 | Receivables aging | kitna lena, kitna late, bade customer | receivables |
| 3 | Payables aging | kitna dena, kitna late, bade vendor | payables |
| 4 | Production output (KG) | good vs scrap, scrap % | production_output |
| 4 | Machines | running / free / hold / unavailable | dashboard |
| 5 | Open production orders | stage, progress, due date, late | production_orders |
| 5 | Sales pipeline | quotation -> order -> dispatch -> invoice -> paisa | quotations |
| 6 | Top customers, Top products | is period ki bikri | invoices |
| 6 | Stock value by type | store / QC / WIP / finished / scrap | valuation |
| 7 | Materials to reorder | kam bacha maal | stock |
| 7 | Purchasing | open PO, QC baaki | purchase_orders / inward_qc |

## Niyam
- Sirf padhna; koi entry nahi. Naya table / migration nahi.
- Sales / purchases **GST ke bina**, returns ghata kar. Cancelled / Waiting documents nahi.
- Pichhla period = utne hi din (jaise 1-26 Nov vs 1-26 Oct). Pichhla zero ho to % nahi dikhta.
- Permission backend par: jis panel ki permission nahi uska data banta hi nahi.
- Data na ho to panel me saaf "no data" line, khaali dabba nahi.
- Charts bina kisi library ke (HTML/CSS/SVG); hover par value, aur "Show as table".

- "To receive / To pay" ke bars me "Opening / other balance" bhi aata hai; advance alag line me (total se pehle hi ghata hua).

## Status (26 Nov)
BUILT local, commit nahi hua. DB copy par test: chaaro period, galat period, Machine board tab, sirf `dashboard` permission wala user (paisa nahi dikhta). `mockups/owner_overview.html` purana v1 hai.

## Abhi nahi
Department-wise alag dashboard, custom date range, export, notifications.

## Files
`app/dashboard/overview.py` (data), `templates/overview.html` (UI), `templates/_dashboard_tabs.html`.
