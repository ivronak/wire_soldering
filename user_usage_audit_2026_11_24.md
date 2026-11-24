# ERP me "User" kahan kahan use ho raha hai — audit (2026-11-24)

Sirf padha gaya (code grep + models), kuch badla nahi. Maksad: dekhna ki ERP me kaunsi jagah "kaun ne kiya" / user ka naam / user dropdown aana chahiye,
aur wahan **Developer user dikhna / chunna nahi chahiye**.

## 1. Asli `users` table abhi sirf yahan use hoti hai

| Jagah | Kya hota hai | Developer ka haal |
|---|---|---|
| Users screen (`app/auth/admin_users.py`) | list / add / edit / reset / activate | Developer sirf Developer ko dikhta hai (`service.visible_users_query`) — theek |
| Roles list (`admin_roles.py`) | role ke saamne "Users" ginti | Developer role non-Developer ko dikhta hi nahi — theek |
| Sidebar (`_sidebar.html`) | logged-in user ka naam + role | apna hi naam — theek |
| `audit_log.actor_user_id` + `actor_label` | har admin kaam ka actor (naam + masked mobile text me bhi) | Audit screen sirf Developer ko — theek |
| `users.created_by_id` | kisne user banaya | andar ki baat, kahin dikhta nahi |

`models.py` me `users.id` par sirf **2 foreign key** hain (upar ke last 2). Baaki poore ERP me koi table `users` se juda nahi.

## 2. "Kaun ne kiya" sab FREE TEXT hai (user se juda nahi) — 10 columns

Inme user likhta hai (type karke), dropdown nahi. Isliye naam galat / alag-alag spelling ho sakti hai, aur kisi login se link nahi.

| Module | Model.column | Form label | Kahan dikhta hai |
|---|---|---|---|
| Inward QC | `InwardQC.inspector` (zaroori) | Inspector * | QC list/view, PO docket |
| Material issue | `MaterialIssue.issued_by`, `received_by` | Issued by (store) / Received by (production) | issue list, print slip, variance |
| Material return | `MaterialReturn.returned_by` | Returned by | list, print |
| Write-off | `MaterialWriteOff.written_off_by` (zaroori) | Who is responsible? * | variance page |
| Routing stage | `ProductionOrderStage.operator` | Operator (datalist = purane likhe naam) | routing, dashboard, scrap labels |
| Production output | `ProductionOutput.recorded_by`, `reviewed_by` | Recorded by / reviewed "Your name" | output list+print, variance review |
| Machine extra hours | `MachineExtraHours.set_by` | (dashboard form me bharta hai) | dashboard |
| Stage Lab QC | `StageLabQC.tested_by` (zaroori) | Tested by * | TC print |

Auto-bharne wale text: `"Auto-issue"` (material_issues/routes.py, routing/routes.py check bhi karta hai), tour/demo me `"Demo operator"`, `"Demo lab"`.

Do jagah "dropdown jaisa" dikhta hai par user table se nahi aata: routing `operators` aur dashboard `operators` = purane likhe naamon ki distinct list (datalist).

## 3. Jahan "kaun ne kiya" record hi nahi hota

Business documents (Quotation, PO, GRN, Purchase invoice, Sales invoice, Receipt, Credit note, Dispatch, Production order, Stock adjustment/transfer, Opening stock...)
par **created_by / approved_by / cancelled_by column hai hi nahi** (grep: models me sirf upar wale 10 text + 2 FK). Approve / Cancel / Finalize / Release kisne dabaya — kahin save nahi.

## 4. Developer wala rule — abhi kya hai, kya chahiye

- Abhi ek hi helper hai: `service.visible_users_query(actor)` — Developer ko sirf Developer dekhta hai (Admin / Manager nahi). Docstring me likha: "har user list / count / dropdown isi se".
- Business dropdown ke liye alag rule chahiye: **active users, jinka role Developer nahi** — chahe dekhne wala Developer ho (aap ne bola "developer ke sivay").
  Suggestion: naya helper `service.pickable_users()` = `is_active` + role `system_key != developer` (Admin aur custom roles dono aayenge).
- Purane records me naam text me bachega (snapshot), taaki user rename / deactivate hone par history na bigde.

## 5. Suggested approach (agar dropdown banana ho)

1. Har field me naya nullable `<field>_user_id` (FK users.id) + purana text column **snapshot** ke roop me rakho (migration safe, purana data na tute).
2. Form me `<select>` = `pickable_users()`; save par `*_user_id` + naam text dono.
3. Print / list me wahi text snapshot dikhe.
4. Naye business docs par `created_by_id` (aur approve / cancel par `*_by_id`) — audit trail ke liye.
5. Server par validate: chuni hui id `pickable_users()` me honi chahiye (Developer id chhup ke bheji to reject).

## 6. Faisla jo aap ka hai

Shop-floor ke log (operator, lab tester, store wala) ke paas ERP login **hota hi nahi** ho sakta — dropdown me tab wo aayenge nahi.
Isliye har field ke liye tay karna hoga: (a) sirf login-wale users dropdown me, (b) text hi rahe (shop-floor naam), (c) dono: dropdown + "Other (type name)".
