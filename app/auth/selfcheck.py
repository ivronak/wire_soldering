# Phase 0: guard ka self-check. Har url_map rule ka koi permission rule hona chahiye, aur rule ki saari keys registry me asli hon.
# Naya route / blueprint jod ke guard_map me na likha ho to ye fail hota hai (test me chalao) — warna wo URL deny-by-default band rahega.
# Chalane ka tarika (test script ya terminal): flask --app run selfcheck-auth   (ya python: from app.auth.selfcheck import problems)
from app.auth import guard_map
from app.auth import registry as R


def problems(app):
    found = []
    all_keys = R.all_keys()
    seen_endpoints = set()
    for rule in app.url_map.iter_rules():
        seen_endpoints.add(rule.endpoint)
        methods = sorted(rule.methods - {"HEAD", "OPTIONS"}) or ["GET"]
        for method in methods:
            resolved = guard_map.resolve(rule.endpoint, method)
            if resolved is None:
                found.append("UNMAPPED: %s %s (%s)" % (method, rule.rule, rule.endpoint))
                continue
            for key in resolved.keys:
                if key not in all_keys:
                    found.append("UNKNOWN KEY %r for %s" % (key, rule.endpoint))
            if resolved.kind == "page" and not resolved.keys:
                found.append("PAGE RULE WITHOUT KEYS: %s" % rule.endpoint)
            if resolved.kind == "page" and resolved.level not in (R.LEVEL_VIEW, R.LEVEL_EDIT):
                found.append("BAD LEVEL for %s: %r" % (rule.endpoint, resolved.level))
    # map me likhe endpoints jo app me hain hi nahi (typo / hata diye gaye route)
    for endpoint in (set(guard_map.OVERRIDES) | set(guard_map.MULTI) | guard_map.JSON_ENDPOINTS | guard_map.PARTY_ENDPOINTS |
                     guard_map.PUBLIC | guard_map.LOGIN_ONLY):
        if endpoint not in seen_endpoints:
            found.append("STALE ENTRY in guard_map (no such endpoint): %s" % endpoint)
    # registry ke har sidebar page ka endpoint asli ho aur us page ke rule me wahi key ho
    for page in R.PAGES + R.ADMIN_PAGES:
        endpoint = page["endpoint"]
        if endpoint not in seen_endpoints:
            found.append("REGISTRY page %s: endpoint %s missing" % (page["key"], endpoint))
            continue
        resolved = guard_map.resolve(endpoint, "GET")
        if resolved is None or (resolved.kind == "page" and page["key"] not in resolved.keys):
            found.append("REGISTRY page %s does not match guard rule for %s" % (page["key"], endpoint))
        if resolved is not None and resolved.kind == "developer" and page["key"] not in R.DEVELOPER_ONLY_KEYS:
            found.append("REGISTRY page %s is developer-only in guard but not in DEVELOPER_ONLY_KEYS" % page["key"])
    for blueprint, key in guard_map.BLUEPRINT_PAGE.items():
        if key not in all_keys:
            found.append("BLUEPRINT_PAGE %s -> unknown key %s" % (blueprint, key))
    return found
