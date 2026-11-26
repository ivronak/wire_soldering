# Phase 0 (login + roles): ERP ke saare "pages" ki ek hi list — page key, naam, module, aur uska list-endpoint.
# Role editor ka matrix, sidebar hide/show, aur guard (P0-4) sab isi list se chalenge. Naya page jodna ho to yahin ek row jodo.
# Page key = chhota slug (jaise "units"); endpoint = us page ka Flask list endpoint (jaise "units.units_list").
# Kuch naya register nahi karta aur database ko nahi chhuta — sirf data + chhote helper functions.

LEVEL_VIEW = 1    # sirf dekhna + print
LEVEL_EDIT = 2    # dekhna + add / edit / cancel (sab badlav)
LEVEL_NAMES = {LEVEL_VIEW: "View", LEVEL_EDIT: "View + Edit"}

# Sidebar jaise module order me (base.html ke 6 module). "group" sirf Masters ke andar ka upar-header hai.
MODULES = ["Dashboard", "Masters", "Procurement", "Sales", "Inventory", "Manufacturing", "Accounts"]
ADMIN_MODULE = "Administration"

# (key, label, module, group, endpoint)
_PAGES = [
    ("dashboard", "Dashboard", "Dashboard", None, "dashboard.dashboard_page"),

    ("units", "Units", "Masters", "Common", "units.units_list"),
    ("tax_rates", "Tax rates", "Masters", "Common", "tax_rates.tax_rates_list"),
    ("charges", "Charges", "Masters", "Common", "charges.charges_list"),
    ("states", "States", "Masters", "Common", "states.states_list"),
    ("payment_terms", "Payment terms", "Masters", "Common", "payment_terms.payment_terms_list"),
    ("payment_modes", "Payment modes", "Masters", "Common", "payment_modes.payment_modes_list"),
    ("work_stages", "Work stages", "Masters", "Production", "work_stages.work_stages_list"),
    ("machines", "Machines", "Masters", "Production", "machines.machines_list"),
    ("production_lines", "Production lines", "Masters", "Production", "production_lines.production_lines_list"),
    ("rm_categories", "RM categories", "Masters", "Raw material", "rm_categories.rm_categories_list"),
    ("raw_materials", "Raw materials", "Masters", "Raw material", "raw_materials.raw_materials_list"),
    ("product_categories", "Product categories", "Masters", "Products", "product_categories.product_categories_list"),
    ("products", "Products", "Masters", "Products", "products.products_list"),
    ("warehouses", "Warehouses", "Masters", "Storage", "warehouses.warehouses_list"),
    ("racks", "Racks", "Masters", "Storage", "racks.racks_list"),
    ("vendors", "Vendors", "Masters", "Partners", "vendors.vendors_list"),
    ("vendor_types", "Vendor types", "Masters", "Partners", "vendor_types.vendor_types_list"),
    ("customers", "Customers", "Masters", "Partners", "customers.customers_list"),

    ("purchase_orders", "Purchase orders", "Procurement", None, "purchase_orders.purchase_orders_list"),
    ("grns", "Gate inward / GRN", "Procurement", None, "grns.grns_list"),
    ("inward_qc", "Inward QC", "Procurement", None, "inward_qc.inward_qc_list"),
    ("purchase_invoices", "Purchase invoice", "Procurement", None, "purchase_invoices.purchase_invoices_list"),
    ("purchase_returns", "Purchase return", "Procurement", None, "purchase_returns.purchase_return_list"),

    ("quotations", "Quotations", "Sales", None, "quotations.quotations_list"),
    ("dispatch", "Dispatch", "Sales", None, "dispatch.dispatch_list"),
    ("invoices", "Invoices", "Sales", None, "sales_invoices.invoices_list"),
    ("receipts", "Receipts", "Sales", None, "receipts.receipts_list"),
    ("sales_returns", "Sales returns", "Sales", None, "sales_returns.returns_list"),
    ("receivables", "Receivables", "Sales", None, "aging.receivables_aging"),
    ("statement", "Statement", "Sales", None, "customer_statement.statement_page"),
    ("profit", "Profit", "Sales", None, "sales_profit.profit_page"),

    ("stock", "Stock ledger", "Inventory", None, "inventory.stock_list"),
    ("opening_stock", "Opening stock", "Inventory", None, "opening_stock.opening_stock_list"),
    ("stock_transfers", "Stock transfer", "Inventory", None, "stock_transfers.stock_transfers_list"),
    ("stock_adjustments", "Stock adjustment", "Inventory", None, "stock_adjustments.stock_adjustments_list"),
    ("valuation", "Stock valuation", "Inventory", None, "inventory.stock_valuation"),
    ("finished_goods", "Finished goods", "Inventory", None, "production_output.finished_goods_list"),

    ("production_orders", "Production order", "Manufacturing", None, "production_orders.production_orders_list"),
    ("production_planning", "Production planning", "Manufacturing", None, "production_planning.production_planning_page"),
    ("material_plan", "Material plan", "Manufacturing", None, "material_plan.material_plan_page"),
    ("material_issues", "Material issue", "Manufacturing", None, "material_issues.material_issues_list"),
    ("routing", "Routing / stages", "Manufacturing", None, "routing.routing_list"),
    ("production_output", "Production output", "Manufacturing", None, "production_output.production_output_list"),
    ("scrap", "Scrap / waste", "Manufacturing", None, "scrap.scrap_list"),
    ("variance", "Consumption variance", "Manufacturing", None, "variance.variance_list"),
    ("costing", "Costing", "Manufacturing", None, "costing.costing_page"),
    # Accounts module (A1): abhi sirf Chart of accounts (dekhna). Vouchers / reports aage ke steps me jodenge.
    ("chart_of_accounts", "Chart of accounts", "Accounts", None, "accounts.chart_page"),
    ("vendor_payments", "Vendor payments", "Accounts", None, "vendor_payments.payments_list"),
    ("payables", "Payables", "Accounts", None, "payables.payables_aging"),
    ("vouchers", "Vouchers", "Accounts", None, "vouchers.vouchers_list"),
    ("ledger_statement", "Ledger statement", "Accounts", None, "ledger_statement.statement_page"),
    ("accounts_reports", "Reports", "Accounts", None, "reports.reports_index"),
]

# Administration pages (P0-7 me bane: app/auth/admin_*.py).
# Users / Roles: Admin / Developer ke paas; user ka faisla (23 Nov): Admin chahe to Staff role ko bhi de sakta hai (flow doc 11.1).
# admin_access / audit_log: sirf Developer — kisi Staff ya Admin role me kabhi nahi.
_ADMIN_PAGES = [
    ("users", "Users", ADMIN_MODULE, None, "admin_users.users_list"),
    ("roles", "Roles", ADMIN_MODULE, None, "admin_roles.roles_list"),
    ("admin_access", "Admin access", ADMIN_MODULE, None, "admin_access.access_page"),
    ("audit_log", "Audit log", ADMIN_MODULE, None, "admin_audit.audit_page"),
]
DEVELOPER_ONLY_KEYS = {"admin_access", "audit_log"}

# Special permissions: kisi page ke andar ka ek khaas kaam (page ke Edit se alag). Role me ye sirf "diya hua" hota hai (level EDIT).
# Abhi sirf ek: stock adjustment ka Approve (user ka faisla 23 Nov: sirf Admin / Developer ke paas, kisi starter role me nahi).
_SPECIALS = [
    ("stock_adjustments.approve", "Approve stock adjustments", "Inventory", "stock_adjustments"),
]


def _page(row):
    key, label, module, group, endpoint = row
    return {"key": key, "label": label, "module": module, "group": group, "endpoint": endpoint, "kind": "page"}


PAGES = [_page(r) for r in _PAGES]
ADMIN_PAGES = [_page(r) for r in _ADMIN_PAGES]
SPECIALS = [{"key": k, "label": l, "module": m, "page": p, "kind": "special", "endpoint": None, "group": None} for k, l, m, p in _SPECIALS]

_BY_KEY = {p["key"]: p for p in PAGES + ADMIN_PAGES + SPECIALS}
_BY_ENDPOINT = {p["endpoint"]: p for p in PAGES + ADMIN_PAGES}


def all_keys():
    # Role / ceiling me jo bhi key valid hai (pages + administration + specials)
    return set(_BY_KEY)


def page_keys():
    return [p["key"] for p in PAGES]


def get(key):
    return _BY_KEY.get(key)


def page_for_endpoint(endpoint):
    # Sirf sidebar ke list-endpoint ka page; baaki endpoints ka mapping P0-4 (guard) me aayega
    return _BY_ENDPOINT.get(endpoint)


def staff_assignable_keys():
    # Jo keys kisi Staff role me ho sakti hain: saare pages + users + roles + specials. admin_access / audit_log kabhi nahi.
    return all_keys() - DEVELOPER_ONLY_KEYS


def tree():
    # Role editor ke matrix ke liye: module -> (group) -> pages. Specials apne page ke neeche alag list me.
    out = []
    for module in MODULES + [ADMIN_MODULE]:
        rows = [p for p in PAGES + ADMIN_PAGES if p["module"] == module]
        out.append({"module": module, "pages": rows, "specials": [s for s in SPECIALS if s["module"] == module]})
    return out
