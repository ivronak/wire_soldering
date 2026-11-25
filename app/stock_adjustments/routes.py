# Stock adjustment: gine hue maal aur system ke stock me farak theek karna, ya found / damaged maal likhna.
# Flow: Draft -> Submit (Pending approval) -> Approve (tab stock badalta hai, "Posted"). Cancel sirf Draft / Pending par.
# Reason zaroori (AdjustmentReason, database se). Stock kab / kitna badalta hai: sirf app/inventory/posting.py (post_adjustment).
from datetime import date, datetime

from flask import render_template, Blueprint, request, redirect, url_for, flash

from app.extensions import db
from app.auth import service as auth_service
from app.inventory.lookups import warehouse_lot_options
from app.inventory.posting import balance, post_adjustment, InventoryError
from app.models import AdjustmentReason, StockAdjustment, StockAdjustmentLine, StockLot, StockMovement, Warehouse

stock_adjustments_bp = Blueprint("stock_adjustments", __name__, template_folder="templates")

TYPE_LABELS = {"increase": "Increase (+)", "decrease": "Decrease (−)", "audit": "Physical audit"}


def list_url(tab="pending"):
    return url_for("stock_adjustments.stock_adjustments_list", tab=tab)


@stock_adjustments_bp.route("/stock_adjustments")
def stock_adjustments_list():
    tab = (request.args.get("tab") or "pending").strip().lower()
    if tab != "completed":
        tab = "pending"
    base = StockAdjustment.query.filter(StockAdjustment.is_deleted == False)
    pending = base.filter(StockAdjustment.status.in_(["Draft", "Pending approval"])).order_by(StockAdjustment.id.desc()).all()
    completed = base.filter(StockAdjustment.status.in_(["Posted", "Cancelled"])).order_by(StockAdjustment.id.desc()).all()
    return render_template(
        "stock_adjustments.html", active_nav="stock_adjustments", tab=tab,
        adjustments=pending if tab == "pending" else completed,
        pending_count=len(pending), completed_count=len(completed), type_labels=TYPE_LABELS,
        warehouses=Warehouse.query.filter(Warehouse.is_deleted == False, Warehouse.is_active == True).order_by(Warehouse.name).all(),
        reasons=AdjustmentReason.query.filter_by(is_deleted=False, is_active=True).order_by(AdjustmentReason.id).all(),
        lot_options=warehouse_lot_options(include_empty=True), today=date.today().isoformat(),
    )


def read_adjustment_form():
    # Form padho aur jaanch karo: (data, None) ya (None, "error"). Kuch save nahi hota jab tak (data, None) na mile.
    adj_type = (request.form.get("adj_type") or "").strip()
    if adj_type not in TYPE_LABELS:
        return None, "Choose the adjustment type."
    warehouse_id = request.form.get("warehouse_id", type=int)
    warehouse = db.session.get(Warehouse, warehouse_id) if warehouse_id else None
    if warehouse is None or warehouse.is_deleted or not warehouse.is_active:
        return None, "Choose an active warehouse."
    reason_id = request.form.get("reason_id", type=int)
    reason = db.session.get(AdjustmentReason, reason_id) if reason_id else None
    if reason is None or reason.is_deleted or not reason.is_active:
        return None, "Choose the reason for the adjustment."
    try:
        adj_date = datetime.strptime((request.form.get("adj_date") or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        return None, "Enter a valid date."
    remarks = (request.form.get("remarks") or "").strip()[:255]
    if reason.name == "Other" and not remarks:
        return None, "Write a short note in Remarks when the reason is Other."

    lines = []
    seen = []
    i = 0
    while True:
        lot_id = request.form.get(f"lot_id_{i}", type=int)
        if lot_id is None:
            break
        qty = request.form.get(f"qty_{i}", type=float)
        i += 1
        if qty is None:
            continue                      # qty khaali = ye lot is adjustment me nahi
        if qty < 0:
            return None, "Quantity cannot be negative."
        if adj_type != "audit" and qty == 0:
            continue
        lot = db.session.get(StockLot, lot_id)
        if lot is None:
            return None, "A selected lot was not found."
        if lot_id in seen:
            return None, "The same lot is listed twice."
        seen.append(lot_id)
        if StockMovement.query.filter_by(lot_id=lot.id, warehouse_id=warehouse.id).first() is None:
            return None, f"{lot.lot_code} has never been in {warehouse.name}."
        if adj_type == "decrease":
            on_hand, _value = balance(lot.id, warehouse.id)
            if round(qty, 4) > on_hand:
                return None, f"{lot.lot_code}: only {on_hand:g} is in {warehouse.name}, so you cannot decrease by {qty:g}."
        lines.append((lot, round(qty, 4)))
    if not lines:
        return None, "Enter a quantity for at least one lot."
    return {"type": adj_type, "warehouse": warehouse, "reason": reason, "date": adj_date, "remarks": remarks, "lines": lines}, None


@stock_adjustments_bp.route("/stock_adjustments/add", methods=["POST"])
def stock_adjustments_add():
    data, error = read_adjustment_form()
    if error:
        flash(error, "error")
        return redirect(list_url("pending"))
    year = data["date"].year
    count = StockAdjustment.query.filter(StockAdjustment.adj_no.like(f"SA-{year}-%")).count()
    adjustment = StockAdjustment(
        adj_no=f"SA-{year}-{count + 1:03d}", adj_date=data["date"], adj_type=data["type"], warehouse=data["warehouse"],
        reason=data["reason"], status="Draft", remarks=data["remarks"] or None, is_deleted=False,
        created_by_id=auth_service.actor_id())       # W1: kisne banaya (login user, apne aap)
    db.session.add(adjustment)
    for lot, qty in data["lines"]:
        db.session.add(StockAdjustmentLine(adjustment=adjustment, lot=lot, entered_qty=qty))
    if (request.form.get("adj_action") or "draft").strip() == "submit":
        adjustment.status = "Pending approval"
        adjustment.submitted_by_id = auth_service.actor_id()       # seedha submit kiya to wahi user
    db.session.commit()
    if adjustment.status == "Pending approval":
        flash(f"{adjustment.adj_no} submitted. Stock changes only after it is approved.", "success")
    else:
        flash(f"{adjustment.adj_no} saved as Draft.", "success")
    return redirect(list_url("pending"))


@stock_adjustments_bp.route("/stock_adjustments/submit/<int:adj_id>", methods=["POST"])
def stock_adjustments_submit(adj_id):
    adjustment = StockAdjustment.query.filter_by(id=adj_id, is_deleted=False).first_or_404()
    if adjustment.status != "Draft":
        flash("Only a draft can be submitted.", "error")
        return redirect(list_url("pending"))
    adjustment.status = "Pending approval"
    adjustment.submitted_by_id = auth_service.actor_id()           # W1: kisne approval ke liye bheja
    db.session.commit()
    flash(f"{adjustment.adj_no} submitted for approval.", "success")
    return redirect(list_url("pending"))


@stock_adjustments_bp.route("/stock_adjustments/approve/<int:adj_id>", methods=["POST"])
def stock_adjustments_approve(adj_id):
    adjustment = StockAdjustment.query.filter_by(id=adj_id, is_deleted=False).first_or_404()
    if adjustment.status != "Pending approval":
        flash("Only an adjustment that is pending approval can be approved.", "error")
        return redirect(list_url("pending"))
    try:
        post_adjustment(adjustment)
    except InventoryError as stock_error:
        db.session.rollback()
        flash(str(stock_error), "error")
        return redirect(list_url("pending"))
    adjustment.approval_note = (request.form.get("approval_note") or "").strip()[:255] or None
    adjustment.status = "Posted"
    adjustment.approved_by_id = auth_service.actor_id()            # W1: kisne approve kiya (stock isi se badla)
    db.session.commit()
    flash(f"{adjustment.adj_no} approved and posted. The stock was updated.", "success")
    return redirect(list_url("completed"))


@stock_adjustments_bp.route("/stock_adjustments/cancel/<int:adj_id>", methods=["POST"])
def stock_adjustments_cancel(adj_id):
    adjustment = StockAdjustment.query.filter_by(id=adj_id, is_deleted=False).first_or_404()
    if adjustment.status not in ("Draft", "Pending approval"):
        flash("A posted adjustment cannot be cancelled. Make an opposite adjustment instead.", "error")
        return redirect(list_url("completed"))
    adjustment.status = "Cancelled"
    adjustment.cancelled_by_id = auth_service.actor_id()           # W1: kisne cancel kiya
    db.session.commit()
    flash(f"{adjustment.adj_no} cancelled. The stock was not changed.", "success")
    return redirect(list_url("pending"))
