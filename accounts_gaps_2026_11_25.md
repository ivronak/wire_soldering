# Accounts: kamiyan jo full-flow demo me mili (25 Nov 2026)

Demo DB copy par chala (asli DB ko haath nahi). Ye list demo ke dauran badhti rahegi. Kuch bhi fix nahi kiya, pehle user se poochna hai.

## Product ki kamiyan (decision chahiye)

| # | Kamiya | Asar | Status |
|---|---|---|---|
| 1 | Production (RM -> WIP -> FG, flux bhi) accounts me post nahi hota | Balance sheet me books ka stock aur inventory ka stock alag dikhta hai ("Stock check" note) | Known, decision baaki |
| 2 | ~~Fixed cost sirf Costing me, accounts me voucher nahi~~ **FIXED 25 Nov (uncommitted)**: output post par Journal voucher Dr Stock-in-hand / Cr Fixed Cost Payable (`app/accounts/fixedcost.py`, migration `d3f7a2b9c1e5`, `flask accounts-backfill` purane outputs ke liye). Restate / month Final / cancel par sirf farak ka naya voucher. COGS pehle se batch cost (material + fixed) se banta tha, isliye profit nahi badla; stock aur liability 2,400 badhe, stock-check farak 2,352.94 -> 47.06 | Baaki: asli rent/salary payment ka voucher (Dr Fixed Cost Payable, Cr Bank) user manual Payment/Journal se karega; jin dino output nahi bana un dino ka fixed cost kahin nahi judta |
| 3 | Accounts me alag Receivables page nahi (Sales me aging hai, Payables accounts me hai) | Customers ka bill-wise baaki accounts me ek jagah nahi | User ne kaha Sales me hi rehne do; sirf total accounts me |
| 4 | `/vouchers?type=...` URL se filter kaam nahi karta | Chhota, dropdown se filter chalta hai | Minor |

## Flux ka voucher zaroori hai ya nahi

Flux ka alag voucher zaroori nahi hai. Chemicals aur flux dono "Stock-in-hand" ke hi hisse hain, to RM se flux banne par total stock ka paisa nahi badalta. Asli zaroorat sirf do cheezon ke liye hai:
1. Production me jo fixed cost (aur labour) stock ki value me judta hai, usko accounts me dikhana.
2. Scrap / loss ko write-off karna.
Isliye ek "production voucher" output post par banana theek rahega, flux ke liye alag nahi.

## Demo tooling / app ke bahar ki baatein (bug nahi)

- PO confirm par vendor ka invoice/proforma file lagana padta hai.
- Post bill ek confirm window maangta hai.
- Bank ka opening balance na ho to bank negative dikhta hai.

## Demo me mili chhoti baatein (production form, 25 Nov)

- Production output form me jo qty maine type ki (103 good, 1 scrap), system ne apne hisaab se 102 good + 2 scrap save ki (spool ki gin ke hisaab se). Spooling stage ka scrap aur output form ka scrap ek doosre se kaise judte hain, user ko saaf nahi dikha. Decision/samjhana baaki.
- Routing: "Complete stage" ka form kuch stages me alag extra fields maangta hai (billet weight/count, scrap type + kind). Naye user ko pata nahi chalta kya bharna hai; sirf 10th-level hint text chahiye.
- Melting ke baad lab test + TC upload zaroori hai, tabhi agla stage start hota hai (rule sahi hai, par ek step badh jata hai).
