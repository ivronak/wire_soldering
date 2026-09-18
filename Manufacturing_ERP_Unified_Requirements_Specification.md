# Manufacturing ERP — Unified Master Requirements Specification
### (₹15 Cr+ Turnover / Gujarat, India / Wire Soldering & Wire Harness Manufacturing)

---

## 0. Document Purpose, Scope & Supersession Note

This document is the **single source of truth (SSOT)** for the Dynamic Manufacturing ERP. It merges and reconciles two earlier drafts:

1. `Dynamic_Manufacturing_ERP_Master_Requirements_Specification.md` — the compliance/technical-heavy master spec.
2. `manufacturing_erp_module_wise_phase_flow_requirements-1.md` — the module-wise functional flow document.

**Why a merge was needed:** the two source drafts used the same `Phase N` labels for different content (e.g. Doc-1's Phase 6 = Sales/E-Invoicing, Doc-2's Phase 6 = Lab/QC), and Doc-2 mis-prioritized E-Invoicing/E-Way Bill as a "future integration" even though it is a legal mandate at this turnover. This document is the **only** phase roadmap that should be used going forward — see Section 23. It also fixes a minor HSN-digit inaccuracy, and fills gaps that existed in either source draft alone (TDS/TCS accounting, Fixed Asset Register, Machine Master, amount-based approval matrix, GSTR-9/9C, Non-Functional Requirements).

### How to Use this Document with Claude / AI Engineering Assistants

1. Provide this complete document as system context / master architectural blueprint.
2. Instruct: *"Using this Master Requirements Specification as context, generate an exhaustive, implementation-ready PRD ONLY for Phase [X] (Section 23). Include database schemas, REST/GraphQL API contracts, frontend state management, keyboard event listeners, validation rules, and error states."*
3. Build, test, and deploy phase-by-phase without breaking backward compatibility or the double-entry accounting ledger.
4. Do not reintroduce the old Doc-1 (0–9) or Doc-2 (0–19) phase numbers in new work — always cite Section 23 phase numbers.

---

## 1. Business Profile, Regulatory Scale & Compliance Mandates

### 1.1 Business Profile & Operating Environment

* **Industry Domain:** Discrete Manufacturing (Electric Wire Holders, Wire Soldering, Wire Harness Assemblies, Terminals & Connectors).
* **Architecture Agility:** 100% dynamic and configurable — zero hardcoded materials, products, attributes, QC parameters, or routing stages.
* **Annual Turnover Scale:** ₹15 Crore+ (₹150 Million INR).
* **Jurisdiction:** Gujarat, India. Primary GST State Code: `24`.
* **Currency:** Indian Rupee (₹) with paise precision (2 decimals) and Indian numbering format (`₹15,00,00,000.00`).

> ⚠️ **Compliance disclaimer:** GST/TDS/TCS thresholds and rates below reflect rules understood at the time of writing. Indian statutory thresholds (e.g. e-invoicing turnover limit) have been lowered progressively by CBIC notifications over the years. **Verify current thresholds/rates with a CA or GST practitioner before finalizing the compliance engine**, and make all thresholds/rates admin-configurable rather than hardcoded, so future notification changes don't require a code release.

### 1.2 Mandatory Statutory Compliance Engine (₹15 Cr Turnover Level)

Because turnover exceeds ₹5 Crore, the ERP must natively support these as **core, non-optional** features (see Section 23, Phase 6 — not a "future integration"):

1. **Mandatory B2B E-Invoicing (IRN & Signed QR Code):**
   * Real-time IRN (Invoice Registration Number) generation via IRP (NIC/GSP API).
   * Storage of 64-character IRN, Signed Invoice Data, and Signed QR Code.
   * Auto-rendering of Signed QR on printable tax invoices.
   * Applies to B2B, SEZ, and Export invoices; **also applies to Credit Notes and Debit Notes issued against B2B invoices** — this is frequently missed by first-time implementations and must be built in from Phase 6, not bolted on later.
   * **IRN Cancellation Window:** an e-invoice can only be cancelled via the IRP within **24 hours** of IRN generation. After 24 hours, correction must go through a Credit/Debit Note, not cancellation — the UI must enforce/reflect this window.
   * B2C invoices exempt from IRN; dynamic B2C QR code applies only at a much higher turnover threshold (verify applicability before building).
2. **E-Way Bill Integration (Rule 138 of CGST Rules):**
   * Mandatory for any consignment where value exceeds ₹50,000 — both intra-state (within Gujarat) and inter-state.
   * **Also required for branch/warehouse stock transfers between different GSTINs**, not only customer-facing dispatch.
   * Part-A (Consignor, Consignee, HSN, Value, Tax) and Part-B (Transporter ID, Vehicle No., RR/Airway/Bill of Lading).
   * Direct API sync or JSON export/import compatibility with the NIC E-Way Bill portal.
3. **6-Digit HSN / SAC Code Enforcement:**
   * For turnover > ₹5 Cr, a minimum of 6-digit HSN (goods) / SAC (services) is mandatory on **both B2B and B2C invoices** (not B2B-only — turnover ≤ ₹5 Cr is the tier where B2C HSN is optional).
4. **GST Tax Engine (Intra-State vs Inter-State Auto-Determination):**
   * Supplier State = Customer State (Gujarat `24` → Gujarat `24`): split equally into **CGST + SGST** (e.g. 9%+9% for 18% slab).
   * Supplier State ≠ Customer State: apply **IGST** (e.g. 18%).
   * Reverse Charge Mechanism (RCM) flag for specific inward supplies (transport GTA, legal services, unregistered vendor purchases).
   * GSTR-1, GSTR-3B summary generation, GSTR-2B automated ITC reconciliation, and **GSTR-9 / GSTR-9C annual return support** (GSTR-9C reconciliation statement applies once turnover exceeds the audit threshold — confirm current threshold).
5. **Income Tax TDS / TCS Provisions:**
   * **Section 194Q (TDS on Purchase of Goods):** 0.1% TDS on vendor purchases exceeding ₹50 Lakhs in a FY, applicable once **buyer's** turnover exceeds ₹10 Cr in the preceding FY.
   * **Section 206C(1H) (TCS on Sale of Goods):** 0.1% TCS on receipts from customers exceeding ₹50 Lakhs, applicable once **seller's** turnover exceeds ₹10 Cr, and only if 194Q was not already deducted by the buyer (194Q takes precedence over 206C(1H)).
   * **Scrap Sale TCS (Section 206C(1)):** 1% TCS on factory scrap sales — note this does not apply if the buyer furnishes Form 27C declaring the scrap is for manufacturing/processing, not trading. The system should support recording this declaration to suppress TCS when applicable.
   * This TDS/TCS logic must be implemented in the **Accounting Engine (Section 11)**, not left as a spec-only note — this was a gap in the earlier functional draft.

---

## 2. Core Architectural Principles & Developer Rules

### 2.1 Architectural Principles

1. **Dynamic-First Architecture:** Zero hardcoding of materials, categories, product variants, dimensions, units, taxes, BOM structures, QC parameters, voucher types, departments, roles, or warehouses.
2. **Master-Driven Integrity:** Transactions only reference validated masters. One-time data entry (e.g. "Copper Wire → Category: Raw Material → Default Unit: KG"), reusable across every workflow — only variable transaction data (rate, quantity, discount, tax) is entered at transaction time.
3. **Central, True Double-Entry Accounting Engine:** Accounting is not an isolated module — every financial and inventory movement automatically posts balanced Debit/Credit entries to the General Ledger. No standalone, decoupled inventory records.
4. **Forward and Backward Traceability:** QR-backed end-to-end lineage: Customer Invoice ↔ Delivery Challan ↔ Finished Batch ↔ In-process QC ↔ Machine/Operator ↔ RM Consumption Lot ↔ Inward GRN ↔ Vendor Purchase Invoice.
5. **Keyboard-First Enterprise Ergonomics:** Desktop-optimized, zero-mouse data entry modeled after Tally's speed.
6. **Immutable Transactional Ledger:** Posted vouchers/finalized invoices cannot be hard-deleted — only cancelled, amended, or reversed via formal Debit/Credit Notes or Reversal Vouchers with full audit logging.

### 2.2 Non-Negotiable Developer Rules

| # | Rule | Rationale |
|---|---|---|
| 1 | No hard-coded products | Today Wire Soldering, tomorrow 20+ products |
| 2 | No hard-coded raw materials | Admin adds new materials without a developer |
| 3 | No hard-coded units | KG, GM, PCS, NOS, Meter etc. must be configurable |
| 4 | No hard-coded product attributes | Size/MM/Thickness/Length must be dynamic (JSONB) |
| 5 | Batch traceability is mandatory | Every production batch's raw-material source must be known |
| 6 | Accounting must be double-entry | Every financial transaction posts balanced Dr/Cr |
| 7 | Stock and accounting stay linked | Minimize duplicate manual entry across modules |
| 8 | No free deletion of posted financial transactions | Cancel/reverse/adjustment mechanism only |
| 9 | Role permissions enforced at backend | Hiding a frontend button is not security |
| 10 | Every critical transaction has an audit trail | Who, when, what created/changed/approved must be traceable |

---

## 3. Financial Year (FY) Lifecycle & "March Baki" (Year-End Closing) Engine

### 3.1 Financial Year Structure

* Standard Indian FY: **1 April – 31 March** (e.g. FY 2026-27 = `2026-04-01` to `2027-03-31`).
* Multi-year operation with seamless historical reporting and comparison.

### 3.2 Period Locking & Audit Controls

* Monthly/Quarterly closing freeze — Admin/Accountant can lock dates prior to a threshold.
* Locked periods disallow creation, editing, back-dating, or deletion of invoices/vouchers/stock entries without explicit **multi-factor Super-Admin override**.

### 3.3 "March Baki" / Annual Year-End Closing Workflow

1. **Year-End Provisions & Accruals:** Depreciation JV (SLM/WDV per Companies Act / IT Act — see Fixed Asset Register, Section 12.2), unpaid salaries/electricity/audit fees, bonus provisions, prepaid expense amortization.
2. **Physical Stock vs Book Stock Audit:** Freeze stock counting module → Discrepancy report (Physical vs ERP) → Stock Adjustment Voucher (write-off/gain) linked to Inventory Adjustment Ledger.
3. **Closing Stock Valuation & P&L Transfer:** Closing Stock via FIFO/Weighted Average → Trading A/c & P&L net profit/loss transferred to **Reserves & Surplus / Retained Earnings (Capital Group)**.
4. **Balance Carry-Forward Engine:** All Balance Sheet ledger closing balances (Debtors, Creditors, Bank, Cash, Loans, Fixed Assets, Capital) auto-migrate as **Opening Balances on 1 April** of new FY. P&L ledgers close to zero. Bill-by-bill references carry forward intact with original invoice numbers/aging.
5. **Voucher Numbering Series Reset/Continuation:** Configurable per new FY (e.g. reset to `001/26-27` or continuous).

---

## 4. Master Data Management

### 4.1 Company, Branch, Warehouse & Department

* **Company Master:** Company Name, Legal Name, Address, GSTIN, PAN, CIN, State (Code 24), Country, Financial Year, Currency, Logo, Contact Details.
* **Branch Master:** branch name, state code, GSTIN (own GSTIN if separate registration), active flag.
* **Warehouse Master:** name, type enum — `RM` (Raw Material), `WIP`, `FG` (Finished Goods), `SCRAP`, `QC_HOLD` — location, active flag.
* **Department Master:** Admin, Purchase, Store, Manufacturing, Lab/QC, Sales, Accounts, Management (admin-extensible list).

### 4.2 User Management & Role/Permission

* User creation, login, password policy, active/inactive, department, role, profile.
* **Permission levels:** View, Create, Edit, Delete, Approve, Export, Print, Cancel, Payment, Special Approval.
* Permission model is **module + action + data-scope** based (see full matrix in Section 19).

### 4.3 Vendor & Customer Masters

* **Vendor:** Code, Name, Contact Person, Mobile, Email, Address, GSTIN, PAN, State, Payment Terms, Opening Balance, Bank Details, Documents, Vendor Type, Active/Inactive. Auto-creates a ledger under **Sundry Creditors**.
* **Customer:** Code, Name, Contact, GSTIN, PAN, Address, Payment Terms, Credit Limit, Opening Balance, Bank Details, Documents, Active/Inactive. Auto-creates a ledger under **Sundry Debtors**.

### 4.4 Raw Material Master

* Fields: Code, Name, Category, Description, Base Unit, Alternate Units, Conversion, Reorder Level, Min/Max Stock, HSN, Valuation Method, Active/Inactive.
* **Master price is never fixed** — rate, quantity, discount, tax, freight, other charges are always entered at purchase transaction time.

### 4.5 Unit Master & Conversion Engine

* Dynamic units: KG, Gram, Ton, Piece, Nos, Meter, MM, Liter, Box, Packet, Bag, Set — admin-extensible.
* Standard conversions (e.g. `1 KG = 1000 Gram`) plus **material-specific conversions** where needed.
* **Dual UOM / Catch Weight:** items with variable weight/length (e.g. Copper Wire purchased in KG, issued in Meters/Coils; Solder Wire billed in Rolls, tracked in Grams) with permissible variance margin (±2%, configurable).

### 4.6 Product Master & Dynamic Variant Engine

* Product fields: Code, Name, Category, Description, Base Unit, HSN, Tax, Active/Inactive.
* **Dynamic attributes** stored as JSONB — Size, Thickness/MM, Length, Gauge, Color, Grade — fully product-configurable, not schema-fixed.
* **Variants:** e.g. Small/2MM, Medium/3MM, Large/5MM — each with a unique **SKU** (e.g. `WSH-SM-2MM`).

### 4.7 Machine Master *(new addition)*

Production routing and the Production Floor dashboard (Section 14) reference "Machine/Operator" and "Machine Utilization" — this requires an explicit master:

* Fields: Machine Code, Name, Work Center/Department, Capacity/Rated Output, Installed Date, Status (`Active` / `Under Maintenance` / `Breakdown` / `Retired`), Linked Maintenance Schedule.
* Feeds: Production routing stage assignment, machine-hour cost allocation in BOM overhead, Production Floor Dashboard downtime/utilization metrics.

### 4.8 BOM / Recipe Master

* Multi-level BOM per Product Variant: Primary Raw Materials, Consumables & Chemical Flux (solder paste, solder wire, heat-shrink tubes), Packaging Materials (polybags, boxes, cartons, barcode labels), Allocated Overhead & Labor Rate (machine-hour cost + labor cost per batch).
* Multi-stage routing tracked per work center without data loss.

---

## 5. Procurement / Purchase Cycle

### Flow

```
Purchase Requisition (optional) → Purchase Order → Gate Inward / Challan →
Goods Receipt Note (GRN) → Inward Lab QC →
  [QC Fail → Rejection Memo / Debit Note] ↔ [QC Pass → Stock Inward]
→ Purchase Invoice (on Accepted GRN Qty) → Dr. RM Stock + Dr. Input GST | Cr. Supplier Payable
→ TDS u/s 194Q auto-calc (if applicable) → Supplier Payment → Bill-by-Bill Settlement
```

Where a business doesn't need a formal PO, a **direct Purchase Invoice** is also supported.

### 5.1 Purchase Order & Inward QC

* PO fields include tax split (CGST+SGST or IGST).
* Gate inward captures Delivery Challan No., Transporter, Vehicle No., Gross Weight.
* System generates a pending **GRN**; raw material enters a virtual **"Under QC Inspection"** location (`QC_HOLD` warehouse).
* Lab technician tests inward lots against configured RM QC templates (e.g. copper gauge tolerance, purity, insulation thickness).
* Only accepted quantity moves to the active RM Warehouse (`Available Stock`).
* Rejected quantity generates an automatic **Material Rejection Memo**, preventing incorrect billing on rejected goods.

### 5.2 Purchase Invoice

* Fields: Invoice No., Date, Vendor, Material, Description, Quantity, Unit, Rate, Discount, Tax, Freight, Other Charges, Total, Payment Terms, Attachment, Remarks.
* Generated strictly against **Accepted GRN Quantities**.
* On submit: Stock increase, Stock Ledger entry, Vendor Payable, Accounting Voucher auto-generated.
* TDS u/s 194Q auto-calculated on purchases exceeding ₹50 Lakhs (buyer turnover > ₹10 Cr).

### 5.3 Purchase Return

Flow: `Purchase Invoice → Return → Stock Decrease → Supplier Adjustment (Debit Note)`.
Supports full/partial return, reason capture, return quantity, and accounting adjustment.

---

## 6. Inventory & Warehouse Management

### 6.1 Stock Ledger

Every material/product tracks: Opening, Purchase, Purchase Return, Production Consumption, Production Output, Sales, Sales Return, Adjustment, Transfer, Closing — continuously, per warehouse.

### 6.2 Multi-Warehouse & Transfer

* A material can hold different stock levels across warehouses.
* Warehouse-to-Warehouse Stock Transfer with **transit tracking**; transfers between different GSTIN branches must also trigger E-Way Bill (Section 1.2.2).

### 6.3 Stock Adjustment & Alerts

* Authorized user can Increase/Decrease stock with Reason + Approval.
* Alerts: Low Stock, Reorder Level, Out of Stock, Excess Stock, Expiry/Dormancy.

### 6.4 Valuation Engine

* Continuous real-time valuation via **FIFO** or **Moving Weighted Average**.
* **WIP Ledger:** raw materials consumed move to WIP until Finished Goods are formally recognized upon QC clearance — prevents sudden book-value drops mid-production.

---

## 7. Production / Manufacturing Engine

### Flow

```
Production Order (linked to Sales Order or Stock Plan)
→ Multi-level BOM Resolution → Batch/Lot Number Assignment
→ Issue RM: Dr. WIP | Cr. Raw Material Stock
→ Multi-Stage Routing (Cutting → Soldering → Assembly → Testing)
→ Scrap Logging (Metal Slag, Burnt Wire → Scrap Warehouse)
→ Production Output (Good / Rework / Scrap / Rejected)
```

### 7.1 Production Order & Batch/Lot

* Production Order fields: No., Product, Variant, Planned Qty, BOM, Production Date, Warehouse, Responsible User.
* Every production run gets a unique **Batch/Lot No.** capturing: production date, product, variant, raw material lots consumed, consumed quantity, output quantity, wastage, operator, machine/process, QC status.

### 7.2 Consumption Variance

Planned vs actual consumption tracked per material:

| Material | Planned | Actual | Variance |
|---|---:|---:|---:|
| RM-A | 10 KG | 10.5 KG | +0.5 KG |
| RM-B | 5 KG | 4.8 KG | −0.2 KG |

### 7.3 Scrap Management

* **Process Loss (invisible):** evaporation, cutting trim within tolerance — not separately inventoried.
* **Saleable Scrap:** physical metal/plastic waste, logged into a dedicated **Scrap Warehouse** in KGs.
* Scrap disposal creates a **Scrap Tax Invoice** with applicable GST (verify current rate per scrap HSN — not uniformly 18%) and 1% TCS under Section 206C(1), subject to Form 27C exemption (Section 1.2.5).

---

## 8. Lab / Quality Control (QC)

### 8.1 QC Templates & Entry

* Lab users see only authorized QC functions.
* **Dynamic, product-wise QC parameters** (admin/QC manager extensible) — e.g. for Wire Soldering: Thickness, Strength, Weight, Finish, Dimension, Electrical/functional parameter, Visual inspection.
* QC Entry fields: Batch No., Product, Production Date, Raw Material Lot, Vendor Trace, Test Parameters, Actual Value, Standard Value, Pass/Fail, Remarks, Tester, Date/time, Attachment.

### 8.2 QC Decision & Failed Batch Handling

* Status: `Pending`, `Passed`, `Failed`, `Rework`, `Hold`.
* A failed batch **does not** enter saleable Finished Stock. Possible actions: Rework, Scrap, Hold, Re-test.

---

## 9. Finished Goods, Traceability & QR Engine

### 9.1 Finished Goods Recognition

* Only QC-approved production enters saleable Finished Goods Stock.
* Accounting: **Dr. Finished Goods Stock | Cr. Work-in-Progress (WIP)**.
* Inventory Valuation: FIFO or Weighted Average.

### 9.2 QR Code & Traceability

* Unique serialized QR generated per product/batch — the QR carries a **secure unique identifier only**, not raw embedded database data.
* **Internal scan (authorized):** full backward & forward lineage — Finished Product → Production Batch → Raw Material Lots → Purchase → Vendor → QC Test → Production Output → Sales — and reverse trace (RM Lot → which batches → which finished products → which customers).
* **External/customer scan:** only public-safe info — Product, Batch, Manufacturing Date, QC status/certificate where intended, authenticity status. **Vendor costing and accounting data must never be exposed externally.**

---

## 10. Sales, Dispatch & Statutory Compliance

> This phase is a **legal compliance mandate** at ₹15 Cr+ turnover, not an optional/future feature — see Section 1.2.

### Flow

```
Customer Quotation → Sales Order (Credit Limit Check) →
Delivery Challan (Finished Goods Batch Allocation) →
E-Way Bill (Part A & B, Gujarat intra/interstate, > ₹50,000) →
E-Invoice IRN & Signed QR (NIC/IRP API) →
Sales Tax Invoice: Dr. Customer Receivable | Cr. Sales | Cr. Output GST
Stock Depletion: Dr. COGS | Cr. Finished Goods Stock →
Payment Collection & Bill-by-Bill Knock-off
```

### 10.1 Quotation, Sales Order & Delivery

* Quotation: Customer, Product, Variant, Quantity, Rate, Discount, Tax, Validity, Terms, Notes.
* Approved quotation converts to Sales Order.
* Delivery captures Product, Variant, Batch, Quantity, Warehouse, Delivery document.

### 10.2 Sales Invoice & Compliance

* Invoice fields: Customer, Product, Variant, Quantity, Rate, Discount, GST, Other Charges, Total, Payment Terms.
* E-Invoicing: 64-char IRN, Acknowledgment No., Signed QR — including for **Credit/Debit Notes** against B2B invoices, with the **24-hour cancellation window** enforced (Section 1.2.1).
* COGS Recognition: Dr. COGS | Cr. Finished Goods Stock.

### 10.3 Sales Return

Invoice reference, Product, Batch, Quantity, Return reason, Stock adjustment, Credit Note/accounting adjustment.

---

## 11. Tally-Grade Accounting & Voucher Engine

### 11.1 Chart of Accounts (Hierarchical)

Predefined standard Indian groups with unlimited sub-groups: Capital Account (Reserves & Surplus), Current Assets (Bank, Cash-in-hand, Deposits, Loans & Advances, Stock-in-hand, Sundry Debtors), Current Liabilities (Duties & Taxes, Provisions, Sundry Creditors), Fixed Assets, Investments, Loans (Liability), Suspense Account, Sales Accounts, Purchase Accounts, Direct Incomes/Expenses (Manufacturing Expenses, Freight Inward, Factory Power), Indirect Incomes/Expenses (Office Rent, Admin Salaries, Marketing, Depreciation).

### 11.2 Voucher Types & Hotkeys

| Key | Voucher | Purpose |
|---|---|---|
| `F4` | Contra | Cash ↔ Bank, inter-bank transfers |
| `F5` | Payment | Vendor payments, expense disbursement |
| `F6` | Receipt | Customer payments, incoming capital/income |
| `F7` | Journal | Non-cash adjustments, provisions, depreciation |
| `F8` | Sales / Tax Invoice | Commercial sale of goods/services |
| `F9` | Purchase | Commercial purchase of RM/assets/services |
| `Alt+F5` | Debit Note / Purchase Return | Goods return to vendor, rate reduction |
| `Alt+F6` | Credit Note / Sales Return | Goods return from customer, discount |

### 11.3 Bill-by-Bill Settlement

Every Sundry Debtor/Creditor transaction enforces reference allocation:

* `New Ref` — fresh Sales/Purchase invoice.
* `Against Ref` — Payment/Receipt/Credit-Debit note knocking off a specific unpaid invoice.
* `Advance` — money received/paid prior to invoice generation.
* `On Account` — lump-sum without specific invoice assignment.
* **Aging Buckets:** 0–30, 31–60, 61–90, 90+ days from Invoice Due Date (credit-period aware).

### 11.4 Automatic Accounting & TDS/TCS Posting

Purchase, Sales, Purchase/Sales Return, Payments, Receipts all auto-generate their accounting voucher — accountants should not need duplicate manual entry. The TDS (194Q) and TCS (206C(1H), 206C(1)) rules from Section 1.2.5 must post automatically as part of the relevant Purchase/Sales/Receipt voucher, with configurable thresholds and rates (not hardcoded).

### 11.5 Drill-Down Financial Reports

* **Balance Sheet:** Group → Sub-group → Ledger → Monthly Summary → Voucher List → Original Voucher Edit — all collapsible/drill-down.
* **P&L:** Trading A/c (Sales, Opening Stock, Purchases, Direct Expenses, Gross Profit) + P&L (Indirect Expenses, Net Profit).
* **Trial Balance:** double-column Dr/Cr with zero-variance validation.
* **Day Book, Cash Book, Bank Book, Ledger Reports.**
* **Bank Reconciliation (BRS):** auto/manual clearance-date marking against imported bank statements — Matched/Unmatched/Pending status.
* **Purchase/Sales Registers, Stock Summary/Ledger.**

---

## 12. Expenses & Fixed Asset Management

### 12.1 Expenses

Rent, Electricity, Salary, Transport, Maintenance, Office Expenses, Marketing, Miscellaneous — every expense flows: `Expense → Accounting Voucher → Ledger → P&L`.

### 12.2 Fixed Asset Register *(new addition)*

Neither source draft had an explicit Fixed Asset module despite referencing depreciation in March Baki (Section 3.3) and a Fixed Assets group in Chart of Accounts (Section 11.1). Required for a manufacturing business with machinery:

* Fields: Asset Code, Name, Category, Purchase Date, Cost, Useful Life, Depreciation Method (SLM/WDV per Companies Act or IT Act — configurable), Accumulated Depreciation, Branch/Location, Status (`Active`/`Under Maintenance`/`Disposed`/`Sold`), linked Machine Master record where applicable (Section 4.7).
* Auto-generates periodic Depreciation Journal Vouchers feeding the March Baki closing workflow (Section 3.3.1).
* Disposal/Sale of asset posts Dr/Cr entries with gain/loss on disposal.

---

## 13. Financial Reporting, GST Compliance & Year-End Closing

### 13.1 GST Compliance Reports

GSTR-1, GSTR-3B summaries, GSTR-2B ITC Matcher, and **GSTR-9 / GSTR-9C** annual return support (verify current audit threshold applicability — Section 1.1 disclaimer).

### 13.2 "March Baki" Year-End Closing Wizard

UI wizard implementing Section 3.3 end-to-end: Depreciation Entry Automation → Provisions/Accruals/Closing Stock Adjustment → P&L Net Profit/Loss Transfer to Reserves & Surplus → Balance Sheet Closing Balances Carry-Forward → Period Lock/Audit Freeze enforcement.

---

## 14. Dashboards, MIS & Notifications

### 14.1 Dashboards

* **Executive/C-Suite:** Daily Turnover, Collections, Payables, Net Margin, Stock Value.
* **Production Floor:** Daily Output, Scrap Ratio, Machine Utilization (via Machine Master, Section 4.7), WIP value.
* **Purchase:** Purchase value, Pending PO, Vendor payable, Material consumption, Low stock.
* **Sales:** Quotation, Orders, Sales, Collection, Outstanding, Top products/customers.
* **QC:** Pending tests, Passed, Failed, Rework, Batch-wise QC.
* **Accounts:** Receivable, Payable, Cash, Bank, Today's vouchers, GST summary, P&L snapshot.

### 14.2 Notifications

Low Stock, QC Failed/Pending, Payment Due, Customer Outstanding, Vendor Payment Due, Purchase/Sales Approval, Production Completed, Stock Adjustment Approval. **In-app first**; email/WhatsApp/SMS integration is a genuine future-phase item (Section 23, Phase 13).

---

## 15. Approval Workflow Engine

Configurable approval per module: Purchase Request → Approval → PO/Invoice; Production Order → Approval → Production; QC Test → QC Approval → Finished Stock; Quotation → Approval → Order; Payment Request → Approval → Payment Voucher; Stock Adjustment → Approval → Stock Update.

### Amount-Based Approval Matrix *(new addition)*

Both source drafts left approval levels as "future configurable" with no concrete mechanism. Minimum viable model:

* Per company, define threshold tiers (e.g. Payment ≤ ₹25,000 → auto/L1; ₹25,000–₹1,00,000 → L2 approval; > ₹1,00,000 → L2 + L3/Super-Admin).
* Thresholds and approver roles configurable per module (Payment, Stock Adjustment, Purchase, Discount %).
* Escalation/timeout handling if an approver doesn't act within an SLA window (configurable).

---

## 16. Documents, Global Search & UX Utilities

* **Attachments** on all relevant records (vendor invoice, purchase invoice, QC report, product certificate, delivery document, payment proof, customer document, GST document) with history maintained.
* **Global search:** Invoice No., Batch No., QR Code, Vendor, Customer, Material, Product, SKU, Voucher No.
* **List filters:** Date, Status, User, Department, Warehouse — plus Export, Print, Pagination on every list.

---

## 17. Audit Trail, Security & Financial Controls

* **Audit Trail:** Create, Edit, Delete, Approve, Reject, Cancel, Payment, Stock Adjustment, Voucher Alteration — capturing User, Timestamp, IP/device, Module, Old JSON, New JSON.
* **Financial Controls:** posted accounting transactions are never hard-deleted — Cancel/Reverse/Adjustment mechanism only (Section 2.2, Rule 8).
* **Period Lock:** Accounts/Admin can lock a financial period; locked periods block unauthorized backdated entries (multi-factor override only, Section 3.2).
* **Backend-enforced RBAC:** permission checks live in backend middleware guards, never frontend-only (Section 2.2, Rule 9).

---

## 18. Data Import/Export & Opening Balance Migration

### 18.1 Import/Export

Excel/CSV import for Vendors, Customers, Materials, Products, Opening Stock, Opening Balances, Ledgers. Export to Excel/CSV/PDF wherever relevant.

### 18.2 Opening Balance & Migration

* **Opening Stock:** Material/Product + Quantity + Unit + Warehouse.
* **Opening Receivable/Payable:** Customer-wise / Vendor-wise opening balance.
* **Ledger Opening Balance:** Account-wise opening Dr/Cr.

---

## 19. Role & Permission Matrix

| Role | Main Access |
|---|---|
| Super Admin | Full ERP |
| Admin | Full operational + configuration |
| Purchase | Vendors, Purchase, Purchase Return |
| Store | Inventory, Stock Transfer, Stock Adjustment |
| Manufacturing | Production, BOM, Batch, Machine Master |
| Lab/QC | QC, Testing, Batch Traceability |
| Sales | Customers, Quotation, Order, Delivery, Sales |
| Accountant | Accounting, Purchase/Sales accounting, Payments, GST, Reports |
| Management | Dashboard, Reports, MIS |
| Viewer | Read-only selected modules |

Example detail (Purchase User: Vendor View/Create, Purchase Create/Edit, no Accounting/Production access; Lab User: QC Create/Edit, Production View-only, no Accounting access; Admin: full access). Permission is always **module + action + data-scope** based.

---

## 20. Frontend Architecture & Enterprise UX Rules

*(Carried forward unchanged from the technical master draft — this content was accurate and complete.)*

### 20.1 Spatial Physics & Density

* **8-Point Grid:** all margins/paddings/sizes snap to 8px base (`4, 8, 12, 16, 24, 32px`).
* **High Data Density:** compact container padding (`12–20px`); no 100px+ whitespace on transactional screens.
* **Border Geometry:** strict `--radius-sm (4px)` / `--radius-md (8px)`; no pill-shaped inputs/buttons in data grids or forms.

### 20.2 Typography & Numerical Formatting

* Font stack: `Geist`, `Inter`, or `IBM Plex Sans`.
* **Tabular numbers mandatory** (`font-variant-numeric: tabular-nums`) for currency, quantity, batch numbers, percentages.
* Labels `11–12px` weight 500/600 uppercase, `letter-spacing: 0.08em`; data values `13–14px`; headers `16–20px`.

### 20.3 Color Science & Accessibility

* 60-30-10 rule: 60% neutral surface (`#0a0a0f` dark / `#fafaf7` light), 30% card surface (`#111118` dark / `#ffffff` light), 10% brand accent.
* WCAG 2.1 AA/AAA: text contrast > 4.5:1.
* Semantic status colors: Success/QC Passed/Paid `#22c55e`; Warning/Under QC/Partial `#f59e0b`; Error/QC Failed/Overdue `#ef4444`; Info/Draft/Pending `#3b82f6`.

### 20.4 Keyboard Engine & Zero-Mouse Navigation

* `Enter` advances focus; `Shift+Enter`/`Up Arrow` retreats.
* `Esc` closes drawers/dialogs/flyouts; navigates to parent dashboard at screen root.
* `Alt+C` — On-the-fly Master Creation from any party/item selector (slide-over modal, auto-select + refocus on save).
* Universal: `Ctrl+S`/`Ctrl+A` save; `Ctrl+P` print; `Ctrl+K` global command palette; `Alt+D` delete active draft (confirmation required).

### 20.5 Data Grid Physics

* Sticky headers and row actions during scroll.
* DOM virtualization (TanStack Virtual/AG Grid) beyond 200 rows for 10,000+ item registers.
* Drag-reorder, resize, toggle-visibility columns (saved to user profile).
* Right-aligned numeric data and headers.

### 20.6 Print Engine (`@media print`)

Formats invoices/delivery notes/QR labels for thermal and laser printers; strips nav/sidebar/buttons on print; `page-break-inside: avoid` on table rows.

### 20.7 Enterprise Anti-Patterns (Banned)

No glassmorphic blur on data tables; no 3D WebGL/Three.js on transactional screens; no custom cursors/magnetic buttons; no bouncy/elastic/long (>150ms) spring animations during data entry; never convey status via color alone (always pair with text/icon).

---

## 21. Non-Functional Requirements *(new addition)*

Neither source draft addressed these — required for a production ERP spec:

* **Performance:** initial page load < 2s; virtualized grid render < 500ms up to 10,000+ rows.
* **Concurrency/Scalability:** design for the business's expected concurrent internal user count (define with stakeholder — e.g. 50–100 concurrent users across Purchase/Store/Production/Lab/Sales/Accounts); architecture should scale horizontally as branches are added.
* **Availability:** target uptime SLA (e.g. 99.5%) if cloud-hosted.
* **Backup & Disaster Recovery:** automated daily DB backups, defined retention (e.g. 30 days), point-in-time recovery capability, tested restore procedure.
* **Hosting & Data Residency:** cloud (AWS/Azure/GCP Indian region) or on-prem, with data residency in India for statutory compliance.
* **Browser/Device Support:** desktop-first (per keyboard-first UX, Section 20.4), evergreen browsers (Chrome/Edge/Firefox latest 2 versions); responsive tablet support for shop-floor QC/production entry.
* **Security:** TLS in transit, encryption at rest, password policy, session timeout, MFA for Super-Admin and period-lock-override actions (Section 3.2).
* **Statutory Data Retention:** retain GST/accounting records per Indian law (commonly 6–8 years — verify current requirement) with archival strategy that doesn't break historical reporting/drill-down.

---

## 22. Database Schema Architecture (Core Tables & Relations)

```sql
-- 1. Tenants & Organizations
companies (id, legal_name, gstin, pan, state_code, currency, fy_start_month);
branches (id, company_id, branch_name, state_code, gstin, is_active);
warehouses (id, branch_id, name, warehouse_type [RM, WIP, FG, SCRAP, QC_HOLD]);

-- 2. Master Tables
units (id, code, name, is_base_unit);
unit_conversions (from_unit_id, to_unit_id, conversion_factor, is_fixed);
raw_materials (id, code, name, category_id, base_unit_id, hsn_code, reorder_level, valuation_method);
products (id, code, name, category_id, base_unit_id, hsn_code, is_active);
product_variants (id, product_id, sku, attributes_jsonb, min_selling_price);
machines (id, branch_id, code, name, work_center, status, installed_date);
boms (id, product_variant_id, bom_no, revision, batch_size, labor_overhead_cost);
bom_items (id, bom_id, material_id, quantity, unit_id, is_consumable, is_packaging);

-- 3. Inward & Production
purchase_orders (id, po_no, vendor_id, po_date, total_amount, status);
goods_receipt_notes (id, grn_no, po_id, challan_no, vehicle_no, status);
inward_qc_inspections (id, grn_id, lot_no, inspector_id, sample_size, passed_qty, rejected_qty, status);
production_orders (id, order_no, product_variant_id, bom_id, planned_qty, start_date, status);
production_batches (id, batch_no, production_order_id, machine_id, mfg_date, actual_output_qty, scrap_qty, status);
production_consumptions (id, batch_id, material_id, lot_no, planned_qty, actual_qty, cost_allocated);

-- 4. Inventory & Quality
stock_ledger (id, warehouse_id, item_type [RM, FG, SCRAP], item_id, batch_lot_no, qty_in, qty_out, unit_cost, transaction_ref_id);
outward_qc_inspections (id, batch_id, test_date, passed_qty, rejected_qty, test_parameters_jsonb, decision);

-- 5. Sales & Dispatch
sales_orders (id, so_no, customer_id, so_date, total_amount, status);
delivery_challans (id, challan_no, so_id, dispatch_date, transporter_id, vehicle_no, eway_bill_no);
sales_invoices (id, invoice_no, customer_id, irn, signed_qr_code, irn_generated_at, total_taxable, cgst, sgst, igst, total_amount, fy_id);

-- 6. Tally Accounting Core
chart_of_accounts_groups (id, name, parent_group_id, classification [ASSET, LIABILITY, INCOME, EXPENSE]);
ledgers (id, name, group_id, opening_balance, current_balance, gstin, bill_by_bill_enabled);
vouchers (id, voucher_type [CONTRA, PAYMENT, RECEIPT, JOURNAL, SALES, PURCHASE, DEBIT_NOTE, CREDIT_NOTE], voucher_no, date, fy_id, narration, is_cancelled);
voucher_entries (id, voucher_id, ledger_id, debit_amount, credit_amount, entry_sequence);
bill_settlements (id, voucher_entry_id, invoice_ref_id, ref_type [NEW_REF, AGAINST_REF, ADVANCE, ON_ACCOUNT], amount_settled);

-- 7. Assets & Controls (new)
fixed_assets (id, asset_code, name, category, branch_id, purchase_date, cost, useful_life_years, depreciation_method, accumulated_depreciation, status);
approval_matrix (id, company_id, module, action, threshold_min, threshold_max, approver_role, escalation_sla_hours);
approval_requests (id, matrix_id, reference_type, reference_id, requested_by, status, approved_by, approved_at);
```

---

## 23. Unified Phase-by-Phase Roadmap for AI PRD Generation

> **This is the single canonical phase list.** It replaces both the source drafts' Phase 0–9 and Phase 0–19 numbering. Feed one phase at a time to the AI PRD-generation prompt (Section 0).

```
====================================================================================
PHASE 0: FOUNDATION, AUTHENTICATION & MULTI-TENANCY
Objective: Multi-branch schema, RBAC, audit log engine, base design tokens.
Deliverables:
- Company Master (GSTIN 24-Gujarat, PAN, CIN, State Code 24, FY definition).
- Branch & Warehouse hierarchy (RM, WIP, FG, Scrap, QC_HOLD).
- Department Master, User Management, RBAC with backend middleware guards.
- Immutable Audit Trail Logger (User, Timestamp, IP, Module, Old/New JSON).
- Global Design System Tokens & Base Component Library (Section 20).
====================================================================================

====================================================================================
PHASE 1: MASTER DATA MANAGEMENT & DYNAMIC ATTRIBUTES
Objective: Core entity masters, zero hardcoded material/product constraints.
Deliverables:
- Dynamic Unit Master & Conversion Engine (Base/Secondary UOM, Catch Weight).
- Raw Material Master (Code, Category, HSN, Reorder Level, QC Params, Valuation).
- Dynamic Product & Variant Engine (JSONB attributes: Size, MM, Thickness, Gauge, Color).
- Vendor & Customer Masters (GSTIN, PAN, State, Payment Terms, Credit Limits).
- Machine Master (Code, Work Center, Capacity, Status).
- Auto-Ledger Generation (Vendor/Customer creation auto-creates ledger).
====================================================================================

====================================================================================
PHASE 2: PROCUREMENT, GRN & INWARD QC
Objective: Full procurement flow — PO to Inward QC to Supplier Payable.
Deliverables:
- Purchase Order with tax split (CGST+SGST or IGST); direct-invoice path w/o PO.
- Gate Inward Entry & GRN into virtual "Under QC" location.
- Inward Lab QC Inspection (Pass/Reject, Rejection Memo generation).
- Purchase Invoice generation strictly on Accepted GRN Quantities.
- TDS u/s 194Q Auto-Calculation on purchases > ₹50 Lakhs.
- Automatic Posting: Dr. RM Inventory | Dr. Input GST | Cr. Supplier Payable.
- Purchase Return (full/partial, Debit Note).
====================================================================================

====================================================================================
PHASE 3: INVENTORY, WAREHOUSE & STOCK VALUATION
Objective: Multi-warehouse stock ledger, adjustments, valuation engine.
Deliverables:
- Real-time Stock Ledger (Opening, Inward, Outward, Transfer, Closing).
- Warehouse-to-Warehouse Transfer with Transit tracking (+ E-Way Bill if cross-GSTIN).
- Stock Reconciliation & Physical Audit adjustment workflow.
- Valuation Engine: Continuous FIFO and Weighted Average.
- Low stock, Reorder Level, Expiry/Dormancy alerts.
====================================================================================

====================================================================================
PHASE 4: MANUFACTURING ENGINE, BOM, ROUTING & WIP
Objective: Core production lifecycle, multi-stage tracking, WIP accounting.
Deliverables:
- Dynamic BOM per Variant (RM, Consumables, Packaging, Labor/Overhead).
- Production Order & Automated Batch/Lot Numbering.
- Material Requisition & Issue: Dr. WIP | Cr. Raw Material Stock.
- Multi-Stage Routing Tracker (Cutting → Soldering → Assembly → Testing).
- Process Scrap & Waste Logging (auto-move to Scrap Warehouse).
- Planned vs Actual Consumption Variance Analysis.
====================================================================================

====================================================================================
PHASE 5: LAB/QC & FINISHED GOODS TRACEABILITY
Objective: Quality clearance, FG valuation, QR-code lineage.
Deliverables:
- Outward QC Test Templates & Inspection Entry (Electrical, Tensile, Visual).
- Batch Clearance Decision Engine (Passed, Failed, Rework, Quarantine).
- Finished Goods Recognition: Dr. Finished Goods Inventory | Cr. WIP.
- Unique Serialized QR Code Generator & Label Print Layout.
- 2-Tier Traceability Scanner: Internal (full lineage) vs External (public-safe).
====================================================================================

====================================================================================
PHASE 6: SALES, E-WAY BILL & MANDATORY E-INVOICING (₹15 CR SCALE) — CORE, NOT OPTIONAL
Objective: Commercial sales cycle with statutory dispatch compliance.
Deliverables:
- Quotation & Sales Order Management with Customer Credit Limit Checks.
- Delivery Challan with Finished Goods Batch/Lot Allocation.
- E-Way Bill Integration (Part-A & Part-B for consignments > ₹50,000, incl. inter-branch).
- E-Invoicing Engine (NIC/IRP API sync: 64-char IRN, Ack No., Signed QR) incl. Credit/Debit Notes, with 24-hour IRN cancellation window enforcement.
- Sales Tax Invoice: Dr. Customer Receivable | Cr. Sales | Cr. Output GST.
- COGS Recognition: Dr. COGS | Cr. Finished Goods Stock.
- Sales Return / Credit Note.
- Scrap Sales Invoicing with 1% TCS under Section 206C(1) (Form 27C exemption support).
====================================================================================

====================================================================================
PHASE 7: TALLY-GRADE DOUBLE-ENTRY ACCOUNTING & BILL-BY-BILL
Objective: Keyboard-first voucher entry, double-entry ledger, knock-off, TDS/TCS.
Deliverables:
- Voucher Entry Engine (F4 Contra, F5 Payment, F6 Receipt, F7 Journal, F8 Sales, F9 Purchase, Alt+F5/F6).
- Zero-Mouse Keyboard Controller (Enter field-jump, Alt+C quick master, Ctrl+A save).
- Bill-by-Bill Knock-off (New Ref, Against Ref, Advance, On Account).
- Customer/Vendor Outstanding Aging Registers (0-30, 31-60, 61-90, 90+).
- TDS (194Q) / TCS (206C(1H), 206C(1)) auto-posting engine.
- Real-time Ledger Balance Indicator during voucher entry.
====================================================================================

====================================================================================
PHASE 8: FINANCIAL REPORTING, GST COMPLIANCE & MARCH BAKI
Objective: Drill-down reports, GST registers, FY closing.
Deliverables:
- Drill-Down Financial Statements: Trial Balance, Balance Sheet, P&L.
- Cash Book, Bank Book, Day Book, Bank Reconciliation Statement (BRS).
- GST Compliance Reports: GSTR-1, GSTR-3B, GSTR-2B ITC Matcher, GSTR-9/9C.
- "March Baki" Year-End Closing Wizard (Depreciation, Provisions, Closing Stock,
  P&L Transfer to Reserves & Surplus, Balance Carry-Forward, Period Lock).
====================================================================================

====================================================================================
PHASE 9: EXPENSES & FIXED ASSET MANAGEMENT
Objective: Expense-to-P&L flow and asset lifecycle/depreciation tracking.
Deliverables:
- Expense entry (Rent, Electricity, Salary, Transport, Maintenance, Marketing, etc.)
  flowing Expense → Voucher → Ledger → P&L.
- Fixed Asset Register (Asset Master, Depreciation Method SLM/WDV, Accumulated
  Depreciation, Disposal/Sale posting) feeding March Baki depreciation entries.
====================================================================================

====================================================================================
PHASE 10: EXECUTIVE DASHBOARDS, APPROVAL WORKFLOW & NOTIFICATIONS
Objective: MIS metrics, configurable approvals, real-time alerts.
Deliverables:
- Executive, Production Floor, Purchase, Sales, QC, Accounts Dashboards.
- Amount-Based Approval Matrix (Purchase, Production, QC, Sales, Payment, Stock
  Adjustment) with configurable thresholds and escalation SLA.
- Real-time Notifications (Low Stock, Overdue Bills, QC Failures, Approval Triggers) — in-app.
====================================================================================

====================================================================================
PHASE 11: DOCUMENTS, GLOBAL SEARCH & ADVANCED UX
Objective: Attachments, global search, list-level filtering/export.
Deliverables:
- Document/attachment management with history across all transaction types.
- Global search (Invoice, Batch, QR, Vendor, Customer, Material, Product, SKU, Voucher).
- Universal list filters (Date, Status, User, Department, Warehouse) + Export/Print/Pagination.
====================================================================================

====================================================================================
PHASE 12: DATA IMPORT/EXPORT, OPENING BALANCE MIGRATION & AUDIT RECOVERY
Objective: Onboarding tooling and administrative security.
Deliverables:
- Excel/CSV Bulk Import & Export for all masters and transactions.
- Opening Stock / Opening Receivable / Opening Payable / Ledger Opening Balance migration.
- Transaction Cancellation/Reversal Engine (no hard deletes, complete audit trail).
====================================================================================

====================================================================================
PHASE 13: FUTURE INTEGRATIONS (post-MVP, genuinely optional)
Objective: Extend reach beyond the core ERP once Phases 0-12 are stable.
Deliverables:
- WhatsApp / Email / SMS notification channels.
- Payment Gateway integration.
- Barcode/label printer hardware integration.
- Mobile application (companion app for approvals/dashboards/QC entry).
- Third-party accounting export integrations.
====================================================================================
```

---

## 24. Final ERP Module Map

1. Dashboard 2. Company & Business Setup 3. User Management 4. Role & Permission 5. Department 6. Vendor Management 7. Customer Management 8. Raw Material Master 9. Unit & Conversion Master 10. Product Master 11. Product Variant/Attribute Management 12. Machine Master 13. Purchase 14. Purchase Return 15. Inventory/Stock 16. Warehouse 17. Stock Transfer 18. Stock Adjustment 19. BOM/Recipe 20. Production 21. Batch/Lot Management 22. Wastage/Scrap/Rework 23. Lab/QC 24. Finished Goods 25. QR/Barcode Traceability 26. Quotation 27. Sales Order 28. Delivery 29. Sales Invoice 30. Sales Return 31. Payment 32. Receipt 33. Expenses 34. Fixed Asset Register 35. Accounting Ledger 36. Voucher Management 37. GST/Tax 38. Bank Reconciliation 39. Receivable 40. Payable 41. Day Book 42. Ledger Reports 43. Cash/Bank Book 44. Trial Balance 45. Profit & Loss 46. Balance Sheet 47. Stock Reports 48. Purchase/Sales Reports 49. MIS Dashboard 50. Approval Workflow 51. Notifications 52. Document Management 53. Audit Log 54. Import/Export 55. ERP Settings

---

## 25. Verification & Success Criteria

### 25.1 AI PRD-Generation Acceptance Criteria

When generating a PRD for any phase (Section 23), it must:

1. **No Hardcoded Attributes** — JSONB or dynamic relation tables for product variation and QC metrics.
2. **Double-Entry Balance Verification** — every financially-impacting transaction defines exact Dr/Cr ledger entries.
3. **Indian Statutory Accuracy** — explicit CGST/SGST/IGST handling, E-Way Bill fields, E-Invoice IRN schema (incl. CN/DN and 24-hour cancellation).
4. **Zero-Mouse Keyboard Specs** — keycode handlers (`Enter`, `Esc`, `Alt+C`, `Ctrl+A`) detailed in the UI spec.
5. **Bill-by-Bill Integrity** — receivables/payables explicitly tied to invoice reference IDs.

### 25.2 Business Success Criteria

The ERP is successful when:

1. New raw material is added without a developer.
2. New product is added without a code change.
3. New product variant/size/MM is configurable.
4. Purchase invoice auto-updates stock and payable.
5. Actual raw-material consumption is recorded during production.
6. A production batch can be traced back to its raw-material vendor.
7. Finished stock is never saleable without QC/approval clearance.
8. Sales auto-updates stock and receivable.
9. Purchase/Sales returns reflect in both accounting and stock.
10. The accountant gets Tally-style vouchers and reports.
11. Every financial transaction balances in double-entry.
12. QR scan delivers batch/product traceability.
13. Each department sees only authorized data/actions.
14. Admin can configure and control the entire ERP.
15. Adding new products/materials/units in future requires minimal developer dependency.
16. E-Invoicing/E-Way Bill compliance works from day one of Phase 6 go-live — not as a later patch.

---

## 26. Final Product Vision

This software is not just **inventory + accounting software**. It is an integrated:

**Manufacturing + Inventory + Purchase + QC + Sales + Accounting + Traceability ERP**

Core architecture:

> **Masters → Transactions → Stock → Production → QC → Sales → Accounting → Reports → Traceability**

All modules stay data-connected so no transaction is ever manually re-entered across modules.
