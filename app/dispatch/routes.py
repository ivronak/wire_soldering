# Sales S3 — Dispatch: Ordered quotation ka maal customer ko bhejna (Delivery Challan). Tabs: To dispatch / Dispatched / Cancelled.
# Stock ka hisaab app/dispatch/stock.py me. Quotation (Finalize ke baad) aur Finished goods (FG batches) se juda hai.
from datetime import date, datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.inventory.money import q4
from app.models import DeliveryChallan, Quotation
from app.dispatch.stock import DispatchError, availability, batch_view, cancel_challan, create_challan, dispatched_qty, dispatch_state, lent_out, pending_qty
from app.production_orders.scheduler import today_ist

dispatch_bp = Blueprint("dispatch", __name__, template_folder="templates")

TABS = ("todo", "done", "cancelled")


def _batch_choices(line, view):
    # Drawer ke "Choose batches" ke liye: is product ke har batch me kitna maal, kiske order ka, aur is line ko kitna bina reason ke mil sakta hai
    rows = []
    for r in view:
        owner = r["owner"]
        mine = owner is not None and (owner.id == line.id or owner.quotation_id == line.quotation_id)
        order = r["batch"].production_order
        if mine:
            label = f"For {owner.quotation.quote_no}"
        elif owner is not None:
            label = f"Kept for {owner.quotation.quote_no}"
        else:
            label = "In-house / extra stock"
        rows.append({"batch_id": r["batch"].id, "batch_no": r["batch"].batch_no, "prod_no": order.prod_no if order else None, "balance": r["balance"],
                     "label": label, "mine": mine, "free_ok": q4((r["reserved"] if mine else 0) + r["free"]),
                     "borrow_max": r["reserved"] if (owner is not None and not mine) else 0.0, "kept_for": owner.quotation.quote_no if (owner is not None and not mine) else None})
    return rows


def _line_row(line, view):
    # Ek quotation line ka dispatch haal: ordered / gaya / baaki / abhi kitna de sakte hain
    avail = availability(line, view)
    order = line.production_order
    return {"line_id": line.id, "product": line.product.name, "code": line.product.code, "unit": line.product.base_unit.code if line.product.base_unit else "",
            "ordered": line.qty, "dispatched": dispatched_qty(line), "pending": pending_qty(line), "own": avail["own"], "free": avail["free"],
            "available": avail["available"], "prod_no": order.prod_no if order else None, "prod_status": order.status if order else None,
            "batches": _batch_choices(line, view)}


def todo_rows():
    # Ordered quotations jinme abhi kuch dispatch hona baaki hai
    rows = []
    quotations = Quotation.query.filter_by(status="Ordered", is_deleted=False).order_by(Quotation.needed_by_date.is_(None), Quotation.needed_by_date, Quotation.id).all()
    for quotation in quotations:
        views = {}
        lines = []
        for line in quotation.lines:
            if line.product_id not in views:
                views[line.product_id] = batch_view(line.product_id)
            lines.append(_line_row(line, views[line.product_id]))
        if not any(row["pending"] > 0.00005 for row in lines):
            continue
        ready = sum(min(row["pending"], row["available"]) for row in lines)
        rows.append({"q": quotation, "lines": lines, "lent": lent_out(quotation), "state": dispatch_state(quotation), "any_ready": any((row["available"] > 0.00005 or row["batches"]) and row["pending"] > 0.00005 for row in lines),
                     "late": quotation.needed_by_date is not None and quotation.needed_by_date < date.today(), "ready": ready})
    return rows


@dispatch_bp.route("/dispatch")
def dispatch_list():
    tab = (request.args.get("tab") or "todo").strip().lower()
    if tab not in TABS:
        tab = "todo"
    todo = todo_rows()
    challans_ok = DeliveryChallan.query.filter_by(status="Dispatched", is_deleted=False).order_by(DeliveryChallan.id.desc()).all()
    challans_cancelled = DeliveryChallan.query.filter_by(status="Cancelled", is_deleted=False).order_by(DeliveryChallan.id.desc()).all()
    counts = {"todo": len(todo), "done": len(challans_ok), "cancelled": len(challans_cancelled)}
    drawer = [{"id": r["q"].id, "no": r["q"].quote_no, "customer": r["q"].customer.name, "lines": r["lines"]} for r in todo]
    return render_template("dispatch.html", active_nav="dispatch", tab=tab, counts=counts, todo=todo, challans=challans_ok if tab == "done" else challans_cancelled,
                           drawer=drawer, today=today_ist().isoformat(), open_q=request.args.get("q", type=int))


@dispatch_bp.route("/dispatch/add/<int:quotation_id>", methods=["POST"])
def dispatch_add(quotation_id):
    quotation = Quotation.query.filter_by(id=quotation_id, is_deleted=False).first_or_404()
    back = redirect(url_for("dispatch.dispatch_list", q=quotation.id))
    if quotation.status != "Ordered":
        flash("Only a finalized (Ordered) quotation can be dispatched.", "error")
        return redirect(url_for("dispatch.dispatch_list"))
    raw_date = (request.form.get("challan_date") or "").strip()
    try:
        challan_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
    except ValueError:
        flash("Enter a valid dispatch date.", "error")
        return back
    if challan_date > today_ist():
        flash("The dispatch date cannot be in the future.", "error")
        return back
    wanted = {}
    picks = {}
    for line in quotation.lines:
        if request.form.get(f"mode_{line.id}") == "pick":
            # User ne batch khud chune: har batch ka pick_<line>_<batch> qty
            chosen = []
            for row in batch_view(line.product_id):
                raw = (request.form.get(f"pick_{line.id}_{row['batch'].id}") or "").strip()
                if not raw:
                    continue
                try:
                    qty = float(raw)
                except ValueError:
                    flash(f"{line.product.name}: enter a valid quantity for batch {row['batch'].batch_no}.", "error")
                    return back
                if qty < 0:
                    flash(f"{line.product.name}: quantity cannot be negative.", "error")
                    return back
                if qty > 0.00005:
                    chosen.append((row["batch"].id, qty))
            if chosen:
                picks[line] = chosen
            continue
        raw = (request.form.get(f"qty_{line.id}") or "").strip()
        if not raw:
            continue
        try:
            qty = float(raw)
        except ValueError:
            flash(f"{line.product.name}: enter a valid quantity.", "error")
            return back
        if qty < 0:
            flash(f"{line.product.name}: quantity cannot be negative.", "error")
            return back
        if qty <= 0.00005:
            continue
        avail = availability(line)
        if qty > avail["available"] + 0.00005:
            flash(f"{line.product.name}: only {avail['available']:g} is in stock ({avail['own']:g} for this order + {avail['free']:g} extra stock), but {qty:g} was entered. "
                  "To use another quotation's goods, choose the batches.", "error")
            return back
        wanted[line] = qty
    if not wanted and not picks:
        flash("Enter a quantity for at least one product.", "error")
        return back
    try:
        challan = create_challan(quotation, challan_date, wanted, transporter=(request.form.get("transporter") or "").strip()[:100] or None,
                                 vehicle_no=(request.form.get("vehicle_no") or "").strip().upper()[:20] or None,
                                 notes=(request.form.get("notes") or "").strip()[:255] or None,
                                 picks=picks, borrow_reason=(request.form.get("borrow_reason") or "").strip())
    except DispatchError as error:
        db.session.rollback()
        flash(str(error), "error")
        return back
    db.session.commit()
    state = dispatch_state(quotation)
    flash(f"Challan {challan.challan_no} created for {quotation.quote_no}. " + ("All items are dispatched." if state == "Dispatched" else "The balance stays pending."), "success")
    return redirect(url_for("dispatch.dispatch_list", tab="done"))


@dispatch_bp.route("/dispatch/<int:challan_id>/cancel", methods=["POST"])
def dispatch_cancel(challan_id):
    challan = DeliveryChallan.query.filter_by(id=challan_id, is_deleted=False).first_or_404()
    back = redirect(url_for("dispatch.dispatch_list", tab="done"))
    if challan.status != "Dispatched":
        flash("This challan is already cancelled.", "error")
        return back
    if challan.invoice_id is not None:
        flash(f"This challan is billed in invoice {challan.invoice.invoice_no}. Cancel the invoice first.", "error")
        return back
    reason = (request.form.get("reason") or "").strip()[:255]
    if len(reason) < 3:
        flash("Write why the challan is cancelled.", "error")
        return back
    cancel_challan(challan, reason)
    challan.cancelled_at = datetime.utcnow()
    db.session.commit()
    flash(f"Challan {challan.challan_no} cancelled. The goods are back in finished goods stock.", "success")
    return redirect(url_for("dispatch.dispatch_list", tab="cancelled"))


@dispatch_bp.route("/dispatch/<int:challan_id>/print")
def dispatch_print(challan_id):
    challan = DeliveryChallan.query.filter_by(id=challan_id, is_deleted=False).first_or_404()
    return render_template("challan_print.html", c=challan, q=challan.quotation)
