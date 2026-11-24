# Sidebar ka data: registry.py ki page list se module -> (sub-group) -> pages, sirf wahi jo logged-in user dekh sakta hai.
# Template (app/templates/_sidebar.html) isi list ko loop karta hai — isliye naya page registry me jodte hi sidebar me aa jata hai (alag se base.html nahi badalna).
# Yahan sirf data banta hai: koi route, koi DB write nahi. Related: app/auth/registry.py (pages), app/auth/service.py (permissions_of).
from flask import url_for

from app.auth import registry as R, service

# Kuch pages ka active_nav (jo page template bhejta hai) unke page key se alag hai — highlight ke liye mapping
ACTIVE_ALIAS = {"inward_qc": "inwards_qc", "receivables": "aging", "profit": "sales_profit"}

# Module (drawer) ka icon — SVG path ("d"); ek jagah, taaki template chhota rahe
MODULE_ICONS = {
    "Dashboard": "M3 12l9-9 9 9M5 10v10a1 1 0 001 1h3a1 1 0 001-1v-4h4v4a1 1 0 001 1h3a1 1 0 001-1V10",
    "Masters": "M4 7c0-1.657 3.582-3 8-3s8 1.343 8 3-3.582 3-8 3-8-1.343-8-3zm0 0v5c0 1.657 3.582 3 8 3s8-1.343 8-3V7m0 5v5c0 1.657-3.582 3-8 3s-8-1.343-8-3v-5",
    "Procurement": "M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z",
    "Sales": "M13 7h8m0 0v8m0-8l-8 8-4-4-6 6",
    "Inventory": "M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4",
    "Manufacturing": "M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z",
    "Administration": "M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z",
}

_GEAR = ("M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
         "M15 12a3 3 0 11-6 0 3 3 0 016 0z")
_TAG = "M7 7h.01M3 11V6a1 1 0 011-1h5a1 1 0 01.707.293l9 9a1 1 0 010 1.414l-5 5a1 1 0 01-1.414 0l-9-9A1 1 0 013 11z"
_BOX = "M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"
_DOC = "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
_SWAP = "M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"
_COIN = "M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
_CLOCK = "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
_CLIPBOARD = "M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
_PEOPLE = "M17 20h5v-2a4 4 0 00-4-4h-1M9 20H4v-2a4 4 0 014-4h1m6-4a3 3 0 11-6 0 3 3 0 016 0zm6 0a3 3 0 11-6 0"
_LEDGER = "M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"

# Har page ka icon (page key -> SVG path). Jo key yahan nahi, use default icon milta hai.
PAGE_ICONS = {
    "dashboard": MODULE_ICONS["Dashboard"],
    "units": "M3 6l3 12h12l3-12H3zm4 0V4h10v2",
    "tax_rates": "M19 5L5 19M8.5 6.5a2 2 0 11-4 0 2 2 0 014 0zM19.5 17.5a2 2 0 11-4 0 2 2 0 014 0z",
    "charges": _COIN,
    "states": "M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7",
    "payment_terms": _CLOCK,
    "payment_modes": "M3 10h18M5 6h14a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2zm4 8h2",
    "work_stages": "M4 6h16M4 12h10M4 18h14",
    "machines": _GEAR,
    "production_lines": _GEAR,
    "rm_categories": _TAG,
    "raw_materials": _BOX,
    "product_categories": _TAG,
    "products": "M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z",
    "warehouses": "M3 21h18M5 21V10l7-5 7 5v11M9 21v-6h6v6",
    "racks": "M4 5h16M4 12h16M4 19h16M7 5v14M17 5v14",
    "vendors": "M8 7V5a2 2 0 012-2h4a2 2 0 012 2v2m-8 0h8m-9 0h10l1 12H6L7 7z",
    "vendor_types": "M7 7h.01M7 3h5a2 2 0 011.414.586l7 7a2 2 0 010 2.828l-5 5a2 2 0 01-2.828 0l-7-7A2 2 0 013 11V6a2 2 0 012-2z",
    "customers": _PEOPLE,
    "purchase_orders": _DOC,
    "grns": _SWAP,
    "inward_qc": "M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4",
    "purchase_invoices": "M9 14l6-6m-5.5.5h.01m4.99 5h.01M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16l3.5-2 3.5 2 3.5-2 3.5 2z",
    "purchase_returns": "M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6",
    "quotations": _DOC,
    "dispatch": "M8 17a2 2 0 11-4 0 2 2 0 014 0zm12 0a2 2 0 11-4 0 2 2 0 014 0zM2 5h11v10H2zm11 4h4l3 3v3h-7z",
    "invoices": "M9 7h6m-6 4h6m-6 4h3M6 3h12a1 1 0 011 1v16l-3-2-3 2-3-2-3 2V4a1 1 0 011-1z",
    "receipts": "M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z",
    "sales_returns": "M3 10h10a5 5 0 010 10H9M3 10l4-4M3 10l4 4",
    "receivables": _CLOCK,
    "statement": "M4 6h16M4 10h16M4 14h10M4 18h7",
    "profit": "M3 17l6-6 4 4 8-8M14 7h7v7",
    "stock": _LEDGER,
    "opening_stock": _LEDGER,
    "stock_transfers": _SWAP,
    "stock_adjustments": "M12 9v3m0 0v3m0-3h3m-3 0H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z",
    "valuation": _COIN,
    "finished_goods": "M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4",
    "production_orders": _CLIPBOARD,
    "production_planning": "M9 12l2 2 4-4m5 2a9 9 0 11-18 0 9 9 0 0118 0z",
    "material_plan": "M8 7V3m8 4V3M4 11h16M5 5h14a1 1 0 011 1v13a1 1 0 01-1 1H5a1 1 0 01-1-1V6a1 1 0 011-1z",
    "material_issues": _BOX,
    "routing": "M13 10V3L4 14h7v7l9-11h-7z",
    "production_output": "M5 13l4 4L19 7",
    "scrap": "M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16",
    "variance": "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z",
    "costing": "M9 8h6m-6 4h6m-3 4l-3-4m0-8h.01M12 21a9 9 0 100-18 9 9 0 000 18z",
    "users": _PEOPLE,
    "roles": MODULE_ICONS["Administration"],
    "admin_access": "M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4",
    "audit_log": "M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01",
}
DEFAULT_ICON = _DOC


def _slug(text):
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in text).strip("-")


def build_nav(user):
    # Logged-in user ke liye sidebar: [{id, label, icon, count, single, groups: [{id, label, pages: [{key, label, url, icon, active}]}]}]
    # Jis module me user ka koi page nahi, wo list me aata hi nahi. Dashboard ek akela page hai -> single=True (drawer nahi, seedha link).
    if user is None:
        return []
    perms = service.permissions_of(user)
    modules = []
    for module in R.MODULES + [R.ADMIN_MODULE]:
        groups, order = {}, []
        for page in R.PAGES + R.ADMIN_PAGES:
            if page["module"] != module or perms.get(page["key"], 0) < R.LEVEL_VIEW:
                continue
            name = page["group"]
            if name not in groups:
                groups[name] = []
                order.append(name)
            groups[name].append({"key": page["key"], "label": page["label"], "url": url_for(page["endpoint"]),
                                 "icon": PAGE_ICONS.get(page["key"], DEFAULT_ICON), "active": ACTIVE_ALIAS.get(page["key"], page["key"])})
        if not order:
            continue
        module_id = _slug(module)
        modules.append({
            "id": module_id, "label": module, "icon": MODULE_ICONS.get(module, DEFAULT_ICON),
            "count": sum(len(groups[n]) for n in order), "single": module == "Dashboard",
            "groups": [{"id": "%s/%s" % (module_id, _slug(n)) if n else module_id, "label": n, "pages": groups[n]} for n in order],
        })
    return modules
