# Phase 0 (P0-4): har URL (endpoint) ko ek permission rule dena — guard (app/auth/guard.py) isi se faisla karta hai.
# Default: blueprint ka apna page key; GET = View (level 1), POST = Edit (level 2). Jo isse alag hai wo OVERRIDES / MULTI me explicit hai.
# DENY-BY-DEFAULT: jis blueprint ka naam BLUEPRINT_PAGE me nahi, uske saare routes band (403) — naya module bina yahan likhe chalega hi nahi.
# Self-check (app/auth/selfcheck.py) har url_map rule ko yahan se milata hai.
from collections import namedtuple

from app.auth import registry as R

V, E = R.LEVEL_VIEW, R.LEVEL_EDIT

# kind: "public" (bina login), "login" (koi bhi logged-in user), "developer" (sirf Developer),
#       "page" (neeche keys me se kisi ek par level chahiye), "party" (vendor / customer document — party type se tay)
# keys: page keys. Ek se zyada ho to user ke paas INME SE KISI EK par level hona kaafi hai (host-page wala rule, flow doc 3.4).
# json: True = anonymous / 403 par HTML redirect nahi, JSON error do (fetch wale routes).
Rule = namedtuple("Rule", ["kind", "keys", "level", "json"])

# blueprint -> page key (blueprint = module jaisa simple case)
BLUEPRINT_PAGE = {
    "aging": "receivables", "charges": "charges", "costing": "costing", "customer_statement": "statement",
    "customers": "customers", "dashboard": "dashboard", "dispatch": "dispatch", "grns": "grns", "inventory": "stock",
    "inward_qc": "inward_qc", "machines": "machines", "material_issues": "material_issues", "material_plan": "material_plan",
    "opening_stock": "opening_stock", "payment_modes": "payment_modes", "payment_terms": "payment_terms",
    "product_categories": "product_categories", "production_lines": "production_lines", "production_orders": "production_orders",
    "production_output": "production_output", "production_planning": "production_planning", "products": "products",
    "purchase_invoices": "purchase_invoices", "purchase_orders": "purchase_orders", "purchase_returns": "purchase_returns",
    "quotations": "quotations", "racks": "racks", "raw_materials": "raw_materials", "receipts": "receipts",
    "rm_categories": "rm_categories", "routing": "routing", "sales_invoices": "invoices", "sales_profit": "profit",
    "sales_returns": "sales_returns", "scrap": "scrap", "states": "states", "stock_adjustments": "stock_adjustments",
    "stock_transfers": "stock_transfers", "tax_rates": "tax_rates", "units": "units", "variance": "variance",
    "vendor_types": "vendor_types", "vendors": "vendors", "warehouses": "warehouses", "work_stages": "work_stages",
}

# Endpoints jinke bare me "kaun hai" ka sawal hi nahi (login page, static, logout...)
PUBLIC = {"static", "auth.login"}
LOGIN_ONLY = {"home", "auth.logout", "auth.change_password"}
DEVELOPER_ONLY_BLUEPRINTS = {"tour"}       # demo tour: abhi development me hai, Developer-only (flow doc 11 #8)

# JSON / fetch wale endpoints (page ke andar se JS bulata hai): login na ho to HTML redirect ki jagah JSON 401
JSON_ENDPOINTS = {
    "dashboard.machine_detail", "dashboard.machine_assign_check", "dashboard.machine_assign", "dashboard.machine_queue_assign",
    "dashboard.machine_queue_move", "grns.grns_po_lines", "inward_qc.inward_qc_grn_lines", "raw_materials.raw_materials_qc_parameters",
    "production_orders.production_orders_expected", "party_documents.party_documents_list", "party_documents.party_documents_add",
    "party_documents.party_documents_delete",
    # Ye 4 sirf page ke JS (fetch) se chalte hain aur JSON lautate hain (audit 23 Nov): login / permission na ho to JSON 401 / 403
    "raw_materials.raw_materials_qc_parameters_add", "raw_materials.raw_materials_qc_parameters_edit",
    "raw_materials.raw_materials_qc_parameters_delete", "warehouses.warehouses_branches_add",
}

# Page key jo blueprint ke default se alag hai (endpoint -> keys, level). level None = method se (GET=View, POST=Edit)
OVERRIDES = {
    # Finished goods blueprint production_output me hai par sidebar (Inventory) me alag page
    "production_output.finished_goods_list": (("finished_goods",), None),
    # Stock valuation cost dikhata hai, isliye stock ledger se alag key
    "inventory.stock_valuation": (("valuation",), None),
    # GET hai par andar tentative DB write + rollback karta hai (SQLite write-lock) -> Edit
    "dashboard.machine_assign_check": (("dashboard",), E),
    # POST hai aur andar tentative DB insert + rollback hota hai (SQLite write-lock) -> Edit (audit 23 Nov). Sirf New order form bulata hai.
    "production_orders.production_orders_expected": (("production_orders",), E),
    # Form kholna (GET) bhi naya quotation banane ka kaam hai -> Edit
    "quotations.quotations_new": (("quotations",), E),
    # Stock adjustment Approve alag special permission (sirf Admin / Developer, user ka faisla 23 Nov)
    "stock_adjustments.stock_adjustments_approve": (("stock_adjustments.approve",), E),
    # Routing ki scrap photo routing page ki hai, scrap page ki nahi
    "routing.routing_scrap_photo": (("routing",), None),
    # Branch add warehouse form ke andar se
    "warehouses.warehouses_branches_add": (("warehouses",), E),
}

# Ek endpoint kai page se chalta hai (dusre page ka button isko POST karta hai). Inme se kisi ek par level chahiye.
MULTI = {
    # Move / Release / Start / Reschedule ke buttons sirf Production planning page par hain -> sirf planning ka Edit (audit 23 Nov:
    # order-entry clerk (sirf production_orders Edit) queue badal / start nahi kar sakta). Cancel dono page par hai.
    "production_orders.production_orders_move": (("production_planning",), E),
    "production_orders.production_orders_release": (("production_planning",), E),
    "production_orders.production_orders_start": (("production_planning",), E),
    "production_orders.production_orders_cancel": (("production_orders", "production_planning"), E),
    "production_orders.production_orders_reschedule": (("production_planning",), E),
    "material_issues.material_writeoff_add": (("material_issues", "production_output"), E),
    "purchase_returns.purchase_returns_add": (("purchase_returns", "purchase_invoices"), E),
}

PARTY_ENDPOINTS = {
    "party_documents.party_documents_list", "party_documents.party_documents_add",
    "party_documents.party_documents_delete", "party_documents.party_documents_file",
}
PARTY_KEY = {"vendor": "vendors", "customer": "customers"}


def resolve(endpoint, method):
    # (endpoint, HTTP method) -> Rule, ya None (= map me nahi = deny)
    if endpoint is None:
        return None
    mutating = method not in ("GET", "HEAD", "OPTIONS")
    if endpoint in PUBLIC:
        return Rule("public", (), 0, False)
    if endpoint in LOGIN_ONLY:
        return Rule("login", (), 0, False)
    blueprint = endpoint.split(".")[0] if "." in endpoint else endpoint
    json_flag = endpoint in JSON_ENDPOINTS
    if blueprint in DEVELOPER_ONLY_BLUEPRINTS:
        return Rule("developer", (), 0, endpoint in ("tour.tour_info", "tour.tour_order_id") or mutating)
    if endpoint in PARTY_ENDPOINTS:
        return Rule("party", ("vendors", "customers"), E if mutating else V, json_flag)
    if endpoint in MULTI:
        keys, level = MULTI[endpoint]
        return Rule("page", keys, level, json_flag)
    if endpoint in OVERRIDES:
        keys, level = OVERRIDES[endpoint]
        return Rule("page", keys, level if level is not None else (E if mutating else V), json_flag)
    if blueprint in BLUEPRINT_PAGE:
        return Rule("page", (BLUEPRINT_PAGE[blueprint],), E if mutating else V, json_flag)
    from app.auth import admin_map           # Administration pages (users / roles / admin_access / audit_log)
    return admin_map.resolve(endpoint, mutating)
