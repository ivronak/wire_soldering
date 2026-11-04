# Material issue: Released production order ke liye RM store se production (WIP) ko dena.
# Auto-flow: "New issue" button nahi — Pending tab me wo Released production orders aate hain jinka RM dena baaki hai.
# Stock kab / kitna badalta hai: sirf app/inventory/posting.py (issue_to_wip / issue_cancelled).
# Lot automatic FIFO se (purana lot pehle) chunta hai, har lot ki alag line banti hai (traceability).
# Material return: production (WIP) me bacha / galat maal wapas store me — issue ki lot-line se, kabhi issue se zyada nahi.
from datetime import date, datetime

from flask import render_template, Blueprint, request, redirect, url_for, flash, abort

from app.extensions import db
from app.inventory.money import q4
from app.inventory.posting import rm_warehouse_of, wip_warehouse_for, available_lots, issue_to_wip, issue_cancelled, material_return_post, material_return_cancel, InventoryError
from app.models import MaterialIssue, MaterialIssueLine, MaterialReturn, MaterialReturnLine, MaterialWriteOff, ProductionOrder, ProductionOrderLine
from app.production_orders.scheduler import live_schedule

RETURN_REASONS = ["Unused spare (allowance)", "Not needed (excess)", "Wrong material issued", "Order changed", "Other"]

material_issues_bp = Blueprint("material_issues", __name__, template_folder="templates")


def list_url(tab="issue"):
    return url_for("material_issues.material_issues_list", tab=tab)


def reserved_in_drafts(lot_id):
    # Draft issues me is lot ka jitna maal "dena tay" hai par abhi post nahi hua (dusre issue use na kar le)
    total = 0
    for line in MaterialIssueLine.query.filter_by(lot_id=lot_id).all():
        issue = line.issue
        if issue.is_deleted or issue.status != "Draft":
            continue
        total += line.qty
    return round(total, 4)


def returned_lot_ids(order):
    # Is production order ne jin lots ka maal wapas kiya (Posted returns). Client rule: wapas kiya lot dobara issue me pehle nahi lena.
    ids = set()
    if order is None:
        return ids
    for ret in order.returns:
        if ret.is_deleted or ret.status != "Posted":
            continue
        for line in ret.lines:
            ids.add(line.lot_id)
    return ids


def free_lots(raw_material_id, order=None):
    # FIFO: purana lot pehle; Draft issues ka tay kiya maal ghata ke. [(lot, qty_free)]
    # order diya ho to us order ne jo lot return kiya wo sabse aakhir me (agla FIFO lot pehle); sirf agla lot kam pade tab wo kaam aata hai.
    skip = returned_lot_ids(order)
    result = []
    for lot, _store, qty, _value in available_lots(raw_material_id):
        free = round(qty - reserved_in_drafts(lot.id), 4)
        if free > 0.00005:
            result.append((lot, free))
    result.sort(key=lambda row: row[0].id in skip)      # sort stable hai: baaki sab purane-pehle ke order me hi rehte hain
    return result


def issue_plan(order):
    # Panel (JS) ke liye: production order ki har line: kitna chahiye, kitna de chuke, kitna baaki, aur store me kitna free hai
    lines = []
    for line in order.lines:
        material = line.raw_material
        free = sum(qty for _lot, qty in free_lots(line.raw_material_id, order))
        remaining = line.remaining_qty
        available = round(free, 4)
        suggest = round(min(remaining, available), 4)          # default "Issue now": jitna baaki, par store ke free se zyada nahi
        spare = line.allowance_remaining_qty                   # order ka allowance: issue kar sakte ho par zaroori nahi
        suggest_all = round(min(remaining + spare, available), 4)
        lines.append({
            "id": line.id,
            "material": (material.code + " " + material.name) if material else "",
            "name": material.name if material else "", "code": material.code if material else "",
            "unit": material.base_unit.code if material and material.base_unit else "",
            "required": line.required_qty,
            "issued": line.issued_qty,
            "remaining": remaining,
            "available": available,
            "extra_ok": order.status == "In production", "spare": spare, "spare_total": line.allowance_qty, "suggest_all": suggest_all,
            "suggest": suggest, "can_all": suggest > 0, "short": remaining > 0 and available + 0.00005 < remaining,
            "frac": min(line.issued_qty / line.required_qty, 1) if line.required_qty else 0,
        })
    return {"order_id": order.id, "prod_no": order.prod_no,
            "product": (order.product.code + " " + order.product.name) if order.product else "", "lines": lines}


def return_plan(order):
    # Return panel (JS) ke liye: is order ki Posted issue lines jinme se kuch wapas ho sakta hai (lot-wise)
    lines = []
    for issue in sorted(order.issues, key=lambda i: i.id):
        if issue.is_deleted or issue.status != "Posted":
            continue
        for line in issue.lines:
            if line.returnable_qty <= 0:
                continue
            material = line.raw_material
            lines.append({
                "id": line.id, "issue_no": issue.issue_no,
                "material": (material.code + " " + material.name) if material else "",
                "lot": line.lot.lot_code if line.lot else "", "batch": line.lot.vendor_batch_no if line.lot else "",
                "unit": material.base_unit.code if material and material.base_unit else "",
                "issued": line.qty, "returned": line.returned_qty, "returnable": line.returnable_qty,
            })
    return {"order_id": order.id, "prod_no": order.prod_no, "product": (order.product.code + " " + order.product.name) if order.product else "", "lines": lines}


@material_issues_bp.route("/material_issues")
def material_issues_list():
    # Tabs: To issue (queue ke order me orders + draft issues), Issued (history), Returns. Purane ?tab=pending / completed bhi chalte hain.
    tab = (request.args.get("tab") or "issue").strip().lower()
    tab = {"pending": "issue", "completed": "issued"}.get(tab, tab)
    if tab not in ("issue", "issued", "returns"):
        tab = "issue"

    # Queue order me (pehle chal rahe, phir priority se) + raw material ka queue-aware haal (Need to buy / PO coming ...)
    queue, materials, schedule = live_schedule()
    to_issue = [o for o in queue if o.status in ("Released", "In production") and o.issue_status != "Fully issued"]
    # Chalte order ka maal pura issue ho chuka ho tab bhi extra maal (naya maal process me) issue karne ka rasta chahiye
    extra_orders = [o for o in queue if o.status == "In production" and o.issue_status == "Fully issued"]
    can_return = [o for o in queue if o.status in ("Released", "In production") and return_plan(o)["lines"]]

    base = MaterialIssue.query.filter(MaterialIssue.is_deleted == False)
    draft_issues = base.filter(MaterialIssue.status == "Draft").order_by(MaterialIssue.id.desc()).all()
    issues = base.filter(MaterialIssue.status != "Draft").order_by(MaterialIssue.id.desc()).all()
    returns = MaterialReturn.query.filter(MaterialReturn.is_deleted == False).order_by(MaterialReturn.id.desc()).all()

    # Cards ke chhote text / View drawer ka data (issue aur return dono ke liye)
    def lines_text(lines):
        totals = {}
        for line in lines:
            material = line.raw_material
            key = (material.name if material else "?", material.base_unit.code if material and material.base_unit else "")
            totals[key] = round(totals.get(key, 0) + line.qty, 4)
        return " · ".join(f"{name} {qty:g} {unit}".strip() for (name, unit), qty in totals.items())

    issue_text = {i.id: lines_text(i.lines) for i in draft_issues + issues}
    view_data = {}
    for i in draft_issues + issues:
        lines = []
        for line in i.lines:
            row = dict(line.summary)
            row["returned"] = line.returned_qty
            lines.append(row)
        view_data[i.id] = {"no": i.issue_no, "order": i.production_order.prod_no, "date": i.issue_date.strftime("%d %b %Y"), "status": i.status,
                           "remarks": i.remarks or "", "by": " → ".join(x for x in (i.issued_by, i.received_by) if x), "lines": lines}
    return_text = {r.id: lines_text(r.lines) for r in returns}
    return_view = {r.id: {"no": r.return_no, "order": r.production_order.prod_no, "date": r.return_date.strftime("%d %b %Y"), "status": r.status,
                          "remarks": r.remarks or "", "reason": r.reason, "by": r.returned_by or "", "lines": [l.summary for l in r.lines]} for r in returns}

    pending_count = len(to_issue) + len(draft_issues)
    counts = {"issue": pending_count, "issued": len(issues), "returns": len(returns)}
    kpi = {"orders": len(to_issue), "drafts": len(draft_issues),
           "short": len([o for o in to_issue if materials.get(o.id, {}).get("status") in ("coming", "buy")]),
           "returnable": len(can_return)}
    return render_template(
        "material_issues.html", active_nav="material_issues", tab=tab,
        to_issue=to_issue, extra_orders=extra_orders, plans={order.id: issue_plan(order) for order in to_issue + extra_orders},
        return_plans={order.id: return_plan(order) for order in can_return},
        materials=materials, schedule=schedule,
        draft_issues=draft_issues, issues=issues, returns=returns,
        pending_count=pending_count, completed_count=len(issues), counts=counts, kpi=kpi,
        reasons=RETURN_REASONS, today=date.today().isoformat(),
        issue_text=issue_text, view_data=view_data, return_text=return_text, return_view=return_view,
    )


def read_issue_form():
    # Form padho aur poori jaanch yahin: (data, None) ya (None, "error"). Database me kuch nahi likhte jab tak (data, None) na mile.
    order_id = request.form.get("production_order_id", type=int)
    order = db.session.get(ProductionOrder, order_id) if order_id else None
    if order is None or order.is_deleted:
        return None, "Production order not found."
    if order.status not in ("Released", "In production"):
        return None, f"{order.prod_no} is not released yet. Release the production order first."

    try:
        issue_date = datetime.strptime((request.form.get("issue_date") or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        return None, "Enter a valid issue date."
    remarks = (request.form.get("remarks") or "").strip()[:255]
    issued_by = (request.form.get("issued_by") or "").strip()[:60]
    received_by = (request.form.get("received_by") or "").strip()[:60]

    wanted = []          # (production_order_line, qty)
    i = 0
    while True:
        line_id = request.form.get(f"line_id_{i}", type=int)
        if line_id is None:
            break
        qty = request.form.get(f"qty_{i}", type=float)
        i += 1
        if qty is None or qty == 0:
            continue                      # is material ka issue abhi nahi
        if qty < 0:
            return None, "Quantity cannot be negative."
        line = db.session.get(ProductionOrderLine, line_id)
        if line is None or line.production_order_id != order.id:
            return None, "A material line does not belong to this production order."
        name = line.raw_material.name if line.raw_material else "Material"
        unit = line.raw_material.base_unit.code if line.raw_material and line.raw_material.base_unit else ""
        can_issue = round(line.remaining_qty + line.allowance_remaining_qty, 4)          # zaroorat + bacha hua allowance
        extra_ok = order.status == "In production" and bool(remarks)       # chalte order me naya maal laana ho to remark ke saath cap se zyada bhi
        if round(qty, 4) > can_issue and not extra_ok:
            if order.status == "In production":
                return None, f"{name}: {can_issue:g} {unit} can be issued normally. To issue more for a running order, write the reason in Remarks (for example 'extra flux brought in')."
            if not line.allowance_qty:
                return None, f"{name}: only {can_issue:g} {unit} is still to be issued ({line.required_qty:g} needed, {line.issued_qty:g} already issued)."
            return None, f"{name}: only {can_issue:g} {unit} can still be issued ({line.required_qty:g} needed + {line.allowance_qty:g} spare, {line.issued_qty:g} already issued)."
        wanted.append((line, q4(qty), name, unit))
    if not wanted:
        return None, "Enter a quantity for at least one material."

    # FIFO: har material ka maal purane lot se. Ek material do baar nahi (ek line ek baar), isliye free qty line-wise ghat-ti jaati hai
    taken = {}           # lot_id -> is form me pehle se liya hua
    allocation = []      # (production_order_line, lot, qty)
    for line, qty, name, unit in wanted:
        left = qty
        for lot, free in free_lots(line.raw_material_id, order):
            usable = round(free - taken.get(lot.id, 0), 4)
            if usable <= 0:
                continue
            take = min(usable, left)
            allocation.append((line, lot, take))
            taken[lot.id] = round(taken.get(lot.id, 0) + take, 4)
            left = round(left - take, 4)
            if left <= 0.00005:
                break
        if left > 0.00005:
            return None, f"{name}: only {qty - left:g} {unit} is free in the store, but {qty:g} {unit} was asked."
    return {"order": order, "issue_date": issue_date, "remarks": remarks, "issued_by": issued_by, "received_by": received_by, "allocation": allocation}, None


def auto_issue_extra(order, order_line, qty, received_by, remarks):
    """Production ko store se ek click me extra maal (client meeting 2, #14): jaise 500 spool diye the par 520 bane to 20 aur.
    Normal issue jaisa hi: FIFO lot, stock WIP me, naam + reason ke saath. Store me kam ho to InventoryError (kuch save nahi hota)."""
    qty = q4(qty)
    allocation = []
    left = qty
    for lot, free in free_lots(order_line.raw_material_id, order):
        take = min(free, left)
        allocation.append((lot, take))
        left = round(left - take, 4)
        if left <= 0.00005:
            break
    if left > 0.00005:
        name = order_line.raw_material.name if order_line.raw_material else "Material"
        raise InventoryError(f"{name}: {qty:g} more is needed but only {qty - left:g} is free in the store.")
    today = date.today()
    count = MaterialIssue.query.filter(MaterialIssue.issue_no.like(f"MI-{today.year}-%")).count()
    issue = MaterialIssue(issue_no=f"MI-{today.year}-{count + 1:03d}", production_order=order, issue_date=today, status="Draft",
                          remarks=remarks[:255], is_deleted=False, issued_by="Auto-issue", received_by=received_by[:60])
    db.session.add(issue)
    for lot, take in allocation:
        db.session.add(MaterialIssueLine(issue=issue, production_order_line=order_line, raw_material_id=order_line.raw_material_id, lot=lot, qty=take))
    issue_to_wip(issue)
    issue.status = "Posted"
    db.session.flush()
    db.session.expire(order_line)            # issued_qty dobara nikle (nayi issue line ke saath)
    return issue


@material_issues_bp.route("/material_issues/add", methods=["POST"])
def material_issues_add():
    data, error = read_issue_form()
    if error:
        flash(error, "error")
        return redirect(list_url("issue"))

    year = data["issue_date"].year
    count = MaterialIssue.query.filter(MaterialIssue.issue_no.like(f"MI-{year}-%")).count()
    issue_no = f"MI-{year}-{count + 1:03d}"
    issue = MaterialIssue(issue_no=issue_no, production_order=data["order"], issue_date=data["issue_date"],
                          status="Draft", remarks=data["remarks"], is_deleted=False,
                          issued_by=data["issued_by"], received_by=data["received_by"])
    db.session.add(issue)
    for line, lot, qty in data["allocation"]:
        db.session.add(MaterialIssueLine(issue=issue, production_order_line=line, raw_material_id=line.raw_material_id, lot=lot, qty=qty))

    if (request.form.get("issue_action") or "draft").strip() == "post":
        try:
            issue_to_wip(issue)
        except InventoryError as stock_error:
            db.session.rollback()
            flash(str(stock_error), "error")
            return redirect(list_url("issue"))
        issue.status = "Posted"
    db.session.commit()

    if issue.status == "Posted":
        flash(f"Material issue {issue_no} posted: the material moved from the store to WIP.", "success")
        return redirect(list_url("issued"))
    flash(f"Material issue {issue_no} saved as Draft. Post it from the Pending list to move the stock.", "success")
    return redirect(list_url("issue"))


@material_issues_bp.route("/material_issues/post/<int:issue_id>", methods=["POST"])
def material_issues_post(issue_id):
    issue = MaterialIssue.query.filter_by(id=issue_id, is_deleted=False).first_or_404()
    if issue.status != "Draft":
        flash("Only a draft issue can be posted.", "error")
        return redirect(list_url("issued"))
    try:
        issue_to_wip(issue)
    except InventoryError as stock_error:
        db.session.rollback()
        flash(str(stock_error), "error")
        return redirect(list_url("issue"))
    issue.status = "Posted"
    db.session.commit()
    flash(f"Material issue {issue.issue_no} posted: the material moved from the store to WIP.", "success")
    return redirect(list_url("issued"))


@material_issues_bp.route("/material_issues/cancel/<int:issue_id>", methods=["POST"])
def material_issues_cancel(issue_id):
    issue = MaterialIssue.query.filter_by(id=issue_id, is_deleted=False).first_or_404()
    if issue.status == "Cancelled":
        flash("This issue is already cancelled.", "error")
        return redirect(list_url("issued"))
    was_posted = issue.status == "Posted"
    if was_posted:
        returned = [line for line in issue.lines if line.returned_qty > 0]
        if returned:
            flash(f"{issue.issue_no} has material that was already returned to the store. Cancel those returns first, then cancel the issue.", "error")
            return redirect(list_url("issued"))
        issue_cancelled(issue)          # stock wapas store me (ulti rows)
    issue.status = "Cancelled"
    db.session.commit()
    flash(f"Material issue {issue.issue_no} cancelled." + (" The material went back to the store." if was_posted else ""), "success")
    return redirect(list_url("issue" if not was_posted else "issued"))


# ======================= Material return (WIP -> store) =======================
def read_return_form():
    # (data, None) ya (None, "error"). Jab tak (data, None) na mile, database me kuch nahi likhte.
    order_id = request.form.get("production_order_id", type=int)
    order = db.session.get(ProductionOrder, order_id) if order_id else None
    if order is None or order.is_deleted:
        return None, "Production order not found."
    if order.status not in ("Released", "In production"):
        return None, f"Material can be returned only for a released or running production order ({order.prod_no} is {order.status})."
    try:
        return_date = datetime.strptime((request.form.get("return_date") or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        return None, "Enter a valid return date."
    if return_date > date.today():
        return None, "The return date cannot be in the future."
    reason = (request.form.get("reason") or "").strip()
    if reason not in RETURN_REASONS:
        return None, "Choose why the material is being returned."
    remarks = (request.form.get("remarks") or "").strip()[:255]
    returned_by = (request.form.get("returned_by") or "").strip()[:60]

    wanted = []
    seen = set()
    i = 0
    while True:
        line_id = request.form.get(f"issue_line_id_{i}", type=int)
        if line_id is None:
            break
        qty = request.form.get(f"qty_{i}", type=float)
        i += 1
        if qty is None or qty == 0:
            continue
        if qty < 0:
            return None, "Quantity cannot be negative."
        if line_id in seen:
            return None, "The same lot line appears twice."
        seen.add(line_id)
        line = db.session.get(MaterialIssueLine, line_id)
        if line is None or line.issue.production_order_id != order.id or line.issue.is_deleted:
            return None, "A lot line does not belong to this production order."
        name = line.raw_material.name if line.raw_material else "Material"
        unit = line.raw_material.base_unit.code if line.raw_material and line.raw_material.base_unit else ""
        if round(qty, 4) > line.returnable_qty:
            return None, f"{name} ({line.lot.lot_code}): only {line.returnable_qty:g} {unit} can be returned ({line.qty:g} issued, {line.returned_qty:g} already returned)."
        order_line = line.production_order_line
        if order_line.used_qty is not None:
            # Stage ki use likh di gayi: use hua maal wapas nahi ho sakta, sirf bacha hua (issued - use)
            already = sum(q for ol, q in wanted if ol.production_order_line_id == order_line.id)
            if round(already + qty, 4) > order_line.leftover_qty + 0.00005:
                return None, f"{name}: {order_line.used_qty:g} {unit} was used in production, so only {order_line.leftover_qty:g} {unit} can go back to the store."
        if return_date < line.issue.issue_date:
            return None, f"The return date cannot be before the issue date ({line.issue.issue_date.strftime('%d %b %Y')})."
        wanted.append((line, q4(qty)))
    if not wanted:
        return None, "Enter a quantity for at least one lot line."
    return {"order": order, "return_date": return_date, "reason": reason, "remarks": remarks, "returned_by": returned_by, "lines": wanted}, None


@material_issues_bp.route("/material_issues/return", methods=["POST"])
def material_returns_add():
    data, error = read_return_form()
    if error:
        flash(error, "error")
        return redirect(list_url("issued"))
    year = data["return_date"].year
    count = MaterialReturn.query.filter(MaterialReturn.return_no.like(f"MR-{year}-%")).count()
    return_no = f"MR-{year}-{count + 1:03d}"
    ret = MaterialReturn(return_no=return_no, production_order=data["order"], return_date=data["return_date"], reason=data["reason"],
                         remarks=data["remarks"], returned_by=data["returned_by"], status="Posted", is_deleted=False)
    db.session.add(ret)
    for line, qty in data["lines"]:
        db.session.add(MaterialReturnLine(material_return=ret, issue_line=line, raw_material_id=line.raw_material_id, lot=line.lot, qty=qty))
    try:
        material_return_post(ret)
    except InventoryError as stock_error:
        db.session.rollback()
        flash(str(stock_error), "error")
        return redirect(list_url("issued"))
    db.session.commit()
    flash(f"Material return {return_no} posted: the material went from WIP back to the store.", "success")
    return redirect(list_url("returns"))


@material_issues_bp.route("/material_issues/writeoff", methods=["POST"])
def material_writeoff_add():
    """Output se pehle bacha hua maal na mile (jaise 80 khali spool kho gaye) to "missing" likho: naam + reason zaroori (client meeting 2, #14).
    Qty line ki used_qty me jud jaati hai (output par WIP se consume, cost FG me), aur record yahin rehta hai — mismatch list / variance me dikhta hai."""
    order = db.session.get(ProductionOrder, request.form.get("production_order_id", type=int) or 0)
    back = redirect(url_for("production_output.production_output_list", tab="ready"))
    if order is None or order.is_deleted or order.status != "In production":
        flash("Material can be written off only for an order that is in production.", "error")
        return back
    by = (request.form.get("written_off_by") or "").strip()[:60]
    reason = (request.form.get("reason") or "").strip()[:255]
    if not by or len(reason) < 3:
        flash("Write who is responsible and the reason for the write-off.", "error")
        return back
    rows = []
    i = 0
    while True:
        line_id = request.form.get(f"line_id_{i}", type=int)
        if line_id is None:
            break
        qty = request.form.get(f"qty_{i}", type=float)
        i += 1
        if not qty:
            continue
        line = db.session.get(ProductionOrderLine, line_id)
        name = line.raw_material.name if line and line.raw_material else "Material"
        if line is None or line.production_order_id != order.id or qty < 0:
            flash("A material line does not belong to this production order.", "error")
            return back
        if round(qty, 4) > line.leftover_qty + 0.00005:
            flash(f"{name}: only {line.leftover_qty:g} is unaccounted for, so {qty:g} cannot be written off.", "error")
            return back
        rows.append((line, q4(qty)))
    if not rows:
        flash("Enter a quantity to write off.", "error")
        return back
    for line, qty in rows:
        db.session.add(MaterialWriteOff(production_order=order, order_line_id=line.id, raw_material_id=line.raw_material_id, qty=qty,
                                        reason=reason, written_off_by=by, write_off_date=date.today()))
        line.used_qty = q4((line.used_qty or 0) + qty)
    db.session.commit()
    flash("Written off as missing: " + "; ".join(f"{q:g} {l.raw_material.base_unit.code if l.raw_material and l.raw_material.base_unit else ''} {l.raw_material.name if l.raw_material else ''}".replace("  ", " ") for l, q in rows)
          + f". It is recorded under {by}.", "success")
    return back


@material_issues_bp.route("/material_issues/return/cancel/<int:return_id>", methods=["POST"])
def material_returns_cancel(return_id):
    ret = MaterialReturn.query.filter_by(id=return_id, is_deleted=False).first_or_404()
    if ret.status != "Posted":
        flash("This return is already cancelled.", "error")
        return redirect(list_url("returns"))
    # Return cancel karne se maal wapas order me ginta hai. Agar wo qty is beech dobara issue ho chuki hai to order ki zaroorat se zyada ho jaayegi — rok do.
    for return_line in ret.lines:
        order_line = return_line.issue_line.production_order_line
        if order_line.issued_qty + return_line.qty > order_line.required_qty + order_line.allowance_qty + 0.00005:
            name = return_line.raw_material.name if return_line.raw_material else "Material"
            flash(f"Cannot cancel: {name} was issued again after this return, so taking {return_line.qty:g} back would go over what the order needs. Cancel the newer issue first.", "error")
            return redirect(list_url("returns"))
    try:
        material_return_cancel(ret)
    except InventoryError as stock_error:
        db.session.rollback()
        flash(str(stock_error), "error")
        return redirect(list_url("returns"))
    ret.status = "Cancelled"
    db.session.commit()
    flash(f"Material return {ret.return_no} cancelled. The material went back to WIP.", "success")
    return redirect(list_url("returns"))


@material_issues_bp.route("/material_issues/print/<int:issue_id>")
def material_issues_print(issue_id):
    # Store ki issue slip (print karne ke liye): lot-wise lines + issued by / received by ki signature jagah
    issue = MaterialIssue.query.filter_by(id=issue_id, is_deleted=False).first_or_404()
    if issue.status == "Cancelled":
        abort(404)
    store, wip = _route_names(issue.lines)
    return render_template("material_issue_print.html", issue=issue, route_from=store, route_to=wip)


def _route_names(lines):
    # Slip par "From / To": maal kis store warehouse se kis WIP warehouse me gaya (pehli lot line se)
    for line in lines:
        try:
            store = rm_warehouse_of(line.lot)
            return store.name, wip_warehouse_for(store).name
        except Exception:
            continue
    return None, None


@material_issues_bp.route("/material_issues/return/print/<int:return_id>")
def material_returns_print(return_id):
    ret = MaterialReturn.query.filter_by(id=return_id, is_deleted=False).first_or_404()
    store, wip = _route_names(ret.lines)
    return render_template("material_return_print.html", ret=ret, route_from=wip, route_to=store)
