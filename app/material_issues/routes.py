# Material issue: Released production order ke liye RM store se production (WIP) ko dena.
# Auto-flow: "New issue" button nahi — Pending tab me wo Released production orders aate hain jinka RM dena baaki hai.
# Stock kab / kitna badalta hai: sirf app/inventory/posting.py (issue_to_wip / issue_cancelled).
# Lot automatic FIFO se (purana lot pehle) chunta hai, har lot ki alag line banti hai (traceability).
from datetime import date, datetime

from flask import render_template, Blueprint, request, redirect, url_for, flash

from app.extensions import db
from app.inventory.money import q4
from app.inventory.posting import available_lots, issue_to_wip, issue_cancelled, InventoryError
from app.models import MaterialIssue, MaterialIssueLine, ProductionOrder, ProductionOrderLine

material_issues_bp = Blueprint("material_issues", __name__, template_folder="templates")


def list_url(tab="pending"):
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


def free_lots(raw_material_id):
    # FIFO: purana lot pehle; Draft issues ka tay kiya maal ghata ke. [(lot, qty_free)]
    result = []
    for lot, _store, qty, _value in available_lots(raw_material_id):
        free = round(qty - reserved_in_drafts(lot.id), 4)
        if free > 0.00005:
            result.append((lot, free))
    return result


def issue_plan(order):
    # Panel (JS) ke liye: production order ki har line: kitna chahiye, kitna de chuke, kitna baaki, aur store me kitna free hai
    lines = []
    for line in order.lines:
        material = line.raw_material
        free = sum(qty for _lot, qty in free_lots(line.raw_material_id))
        lines.append({
            "id": line.id,
            "material": (material.code + " " + material.name) if material else "",
            "unit": material.base_unit.code if material and material.base_unit else "",
            "required": line.required_qty,
            "issued": line.issued_qty,
            "remaining": line.remaining_qty,
            "available": round(free, 4),
        })
    return {"order_id": order.id, "prod_no": order.prod_no,
            "product": (order.product.code + " " + order.product.name) if order.product else "", "lines": lines}


@material_issues_bp.route("/material_issues")
def material_issues_list():
    tab = (request.args.get("tab") or "pending").strip().lower()
    if tab != "completed":
        tab = "pending"

    released = ProductionOrder.query.filter(ProductionOrder.is_deleted == False, ProductionOrder.status.in_(["Released", "In production"])).order_by(ProductionOrder.id.desc()).all()
    to_issue = [order for order in released if order.issue_status != "Fully issued"]

    base = MaterialIssue.query.filter(MaterialIssue.is_deleted == False)
    draft_issues = base.filter(MaterialIssue.status == "Draft").order_by(MaterialIssue.id.desc()).all()
    issues = base.filter(MaterialIssue.status != "Draft").order_by(MaterialIssue.id.desc()).all()

    pending_count = len(to_issue) + len(draft_issues)
    return render_template(
        "material_issues.html", active_nav="material_issues", tab=tab,
        to_issue=to_issue, plans={order.id: issue_plan(order) for order in to_issue},
        draft_issues=draft_issues, issues=issues,
        pending_count=pending_count, completed_count=len(issues),
        result_count=pending_count if tab == "pending" else len(issues),
        today=date.today().isoformat(),
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
        if round(qty, 4) > line.remaining_qty:
            return None, f"{name}: only {line.remaining_qty:g} {unit} is still to be issued ({line.required_qty:g} needed, {line.issued_qty:g} already issued)."
        wanted.append((line, q4(qty), name, unit))
    if not wanted:
        return None, "Enter a quantity for at least one material."

    # FIFO: har material ka maal purane lot se. Ek material do baar nahi (ek line ek baar), isliye free qty line-wise ghat-ti jaati hai
    taken = {}           # lot_id -> is form me pehle se liya hua
    allocation = []      # (production_order_line, lot, qty)
    for line, qty, name, unit in wanted:
        left = qty
        for lot, free in free_lots(line.raw_material_id):
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
    return {"order": order, "issue_date": issue_date, "remarks": remarks, "allocation": allocation}, None


@material_issues_bp.route("/material_issues/add", methods=["POST"])
def material_issues_add():
    data, error = read_issue_form()
    if error:
        flash(error, "error")
        return redirect(list_url("pending"))

    year = data["issue_date"].year
    count = MaterialIssue.query.filter(MaterialIssue.issue_no.like(f"MI-{year}-%")).count()
    issue_no = f"MI-{year}-{count + 1:03d}"
    issue = MaterialIssue(issue_no=issue_no, production_order=data["order"], issue_date=data["issue_date"],
                          status="Draft", remarks=data["remarks"], is_deleted=False)
    db.session.add(issue)
    for line, lot, qty in data["allocation"]:
        db.session.add(MaterialIssueLine(issue=issue, production_order_line=line, raw_material_id=line.raw_material_id, lot=lot, qty=qty))

    if (request.form.get("issue_action") or "draft").strip() == "post":
        try:
            issue_to_wip(issue)
        except InventoryError as stock_error:
            db.session.rollback()
            flash(str(stock_error), "error")
            return redirect(list_url("pending"))
        issue.status = "Posted"
    db.session.commit()

    if issue.status == "Posted":
        flash(f"Material issue {issue_no} posted: the material moved from the store to WIP.", "success")
        return redirect(list_url("completed"))
    flash(f"Material issue {issue_no} saved as Draft. Post it from the Pending list to move the stock.", "success")
    return redirect(list_url("pending"))


@material_issues_bp.route("/material_issues/post/<int:issue_id>", methods=["POST"])
def material_issues_post(issue_id):
    issue = MaterialIssue.query.filter_by(id=issue_id, is_deleted=False).first_or_404()
    if issue.status != "Draft":
        flash("Only a draft issue can be posted.", "error")
        return redirect(list_url("completed"))
    try:
        issue_to_wip(issue)
    except InventoryError as stock_error:
        db.session.rollback()
        flash(str(stock_error), "error")
        return redirect(list_url("pending"))
    issue.status = "Posted"
    db.session.commit()
    flash(f"Material issue {issue.issue_no} posted: the material moved from the store to WIP.", "success")
    return redirect(list_url("completed"))


@material_issues_bp.route("/material_issues/cancel/<int:issue_id>", methods=["POST"])
def material_issues_cancel(issue_id):
    issue = MaterialIssue.query.filter_by(id=issue_id, is_deleted=False).first_or_404()
    if issue.status == "Cancelled":
        flash("This issue is already cancelled.", "error")
        return redirect(list_url("completed"))
    was_posted = issue.status == "Posted"
    if was_posted:
        issue_cancelled(issue)          # stock wapas store me (ulti rows)
    issue.status = "Cancelled"
    db.session.commit()
    flash(f"Material issue {issue.issue_no} cancelled." + (" The material went back to the store." if was_posted else ""), "success")
    return redirect(list_url("pending" if not was_posted else "completed"))
