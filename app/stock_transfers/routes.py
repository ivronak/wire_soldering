# Stock transfer: ek warehouse se doosre warehouse me maal bhejna (lot-wise).
# Draft -> Dispatch (maal source se nikla, "In transit") -> Receive (destination me aaya). Cancel sirf Draft / In transit par.
# Stock kab / kitna badalta hai: sirf app/inventory/posting.py (dispatch_transfer / receive_transfer / transfer_cancelled).
# Rejected maal ko scrap me bhejne ka rasta bhi yahi hai: QC Hold -> Scrap warehouse.
from datetime import date, datetime

from flask import render_template, Blueprint, request, redirect, url_for, flash

from app.extensions import db
from app.auth import service as auth_service
from app.inventory.lookups import warehouse_lot_options
from app.inventory.posting import balance, dispatch_transfer, receive_transfer, transfer_cancelled, InventoryError
from app.models import StockLot, StockTransfer, StockTransferLine, Warehouse

stock_transfers_bp = Blueprint("stock_transfers", __name__, template_folder="templates")


def list_url(tab="pending"):
    return url_for("stock_transfers.stock_transfers_list", tab=tab)


@stock_transfers_bp.route("/stock_transfers")
def stock_transfers_list():
    tab = (request.args.get("tab") or "pending").strip().lower()
    if tab != "completed":
        tab = "pending"
    base = StockTransfer.query.filter(StockTransfer.is_deleted == False)
    pending = base.filter(StockTransfer.status.in_(["Draft", "In transit"])).order_by(StockTransfer.id.desc()).all()
    completed = base.filter(StockTransfer.status.in_(["Received", "Cancelled"])).order_by(StockTransfer.id.desc()).all()
    warehouses = Warehouse.query.filter(Warehouse.is_deleted == False, Warehouse.is_active == True).order_by(Warehouse.name).all()
    return render_template(
        "stock_transfers.html", active_nav="stock_transfers", tab=tab,
        transfers=pending if tab == "pending" else completed,
        pending_count=len(pending), completed_count=len(completed),
        warehouses=warehouses, lot_options=warehouse_lot_options(), today=date.today().isoformat(),
    )


def read_transfer_form():
    # Form padho aur jaanch karo: (data, None) ya (None, "error"). Kuch bhi save nahi hota jab tak (data, None) na mile.
    from_id = request.form.get("from_warehouse_id", type=int)
    to_id = request.form.get("to_warehouse_id", type=int)
    source = db.session.get(Warehouse, from_id) if from_id else None
    destination = db.session.get(Warehouse, to_id) if to_id else None
    for warehouse in (source, destination):
        if warehouse is None or warehouse.is_deleted or not warehouse.is_active:
            return None, "Choose an active From and To warehouse."
    if source.id == destination.id:
        return None, "From and To warehouse must be different."
    try:
        transfer_date = datetime.strptime((request.form.get("transfer_date") or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        return None, "Enter a valid transfer date."

    lines = []
    seen = []
    i = 0
    while True:
        lot_id = request.form.get(f"lot_id_{i}", type=int)
        if lot_id is None:
            break
        qty = request.form.get(f"qty_{i}", type=float)
        i += 1
        if qty is None or qty == 0:
            continue
        if qty < 0:
            return None, "Quantity cannot be negative."
        lot = db.session.get(StockLot, lot_id)
        if lot is None:
            return None, "A selected lot was not found."
        if lot_id in seen:
            return None, "The same lot is listed twice."
        seen.append(lot_id)
        on_hand, _value = balance(lot.id, source.id)
        if round(qty, 4) > on_hand:
            return None, f"{lot.lot_code}: only {on_hand:g} is in {source.name}, but {qty:g} was entered."
        lines.append((lot, round(qty, 4)))
    if not lines:
        return None, "Enter a quantity for at least one lot."
    return {"source": source, "destination": destination, "date": transfer_date, "lines": lines,
            "vehicle": (request.form.get("vehicle_no") or "").strip()[:30],
            "eway": (request.form.get("eway_bill_no") or "").strip()[:30],
            "remarks": (request.form.get("remarks") or "").strip()[:255]}, None


def eway_problem(transfer):
    if transfer.needs_eway and not (transfer.eway_bill_no or "").strip():
        return f"{transfer.transfer_no} goes to a branch with a different GSTIN, so an E-Way Bill number is required before dispatch."
    return None


@stock_transfers_bp.route("/stock_transfers/add", methods=["POST"])
def stock_transfers_add():
    data, error = read_transfer_form()
    if error:
        flash(error, "error")
        return redirect(list_url("pending"))

    year = data["date"].year
    count = StockTransfer.query.filter(StockTransfer.transfer_no.like(f"ST-{year}-%")).count()
    transfer = StockTransfer(
        transfer_no=f"ST-{year}-{count + 1:03d}", transfer_date=data["date"], from_warehouse=data["source"],
        to_warehouse=data["destination"], status="Draft", vehicle_no=data["vehicle"] or None,
        eway_bill_no=data["eway"] or None, remarks=data["remarks"] or None, is_deleted=False,
        created_by_id=auth_service.actor_id())       # W1: kisne banaya (login user, apne aap)
    db.session.add(transfer)
    for lot, qty in data["lines"]:
        db.session.add(StockTransferLine(transfer=transfer, lot=lot, qty=qty))

    if (request.form.get("transfer_action") or "draft").strip() == "dispatch":
        problem = eway_problem(transfer)
        if problem:
            db.session.rollback()
            flash(problem, "error")
            return redirect(list_url("pending"))
        try:
            dispatch_transfer(transfer)
        except InventoryError as stock_error:
            db.session.rollback()
            flash(str(stock_error), "error")
            return redirect(list_url("pending"))
        transfer.status = "In transit"
        transfer.dispatched_by_id = auth_service.actor_id()         # seedha dispatch kiya to wahi user
    db.session.commit()
    if transfer.status == "In transit":
        flash(f"{transfer.transfer_no} dispatched: the goods left {data['source'].name} and are in transit.", "success")
    else:
        flash(f"{transfer.transfer_no} saved as Draft. Dispatch it when the goods leave.", "success")
    return redirect(list_url("pending"))


@stock_transfers_bp.route("/stock_transfers/dispatch/<int:transfer_id>", methods=["POST"])
def stock_transfers_dispatch(transfer_id):
    transfer = StockTransfer.query.filter_by(id=transfer_id, is_deleted=False).first_or_404()
    if transfer.status != "Draft":
        flash("Only a draft transfer can be dispatched.", "error")
        return redirect(list_url("pending"))
    # Draft me E-Way / vehicle baad me bhi bhar sakte hain
    eway = (request.form.get("eway_bill_no") or "").strip()[:30]
    if eway:
        transfer.eway_bill_no = eway
    problem = eway_problem(transfer)
    if problem:
        flash(problem + " Open the transfer, add the E-Way Bill number and dispatch again.", "error")
        return redirect(list_url("pending"))
    try:
        dispatch_transfer(transfer)
    except InventoryError as stock_error:
        db.session.rollback()
        flash(str(stock_error), "error")
        return redirect(list_url("pending"))
    transfer.status = "In transit"
    transfer.dispatched_by_id = auth_service.actor_id()             # W1: kisne dispatch kiya
    db.session.commit()
    flash(f"{transfer.transfer_no} dispatched: the goods left {transfer.from_warehouse.name} and are in transit.", "success")
    return redirect(list_url("pending"))


@stock_transfers_bp.route("/stock_transfers/receive/<int:transfer_id>", methods=["POST"])
def stock_transfers_receive(transfer_id):
    transfer = StockTransfer.query.filter_by(id=transfer_id, is_deleted=False).first_or_404()
    if transfer.status != "In transit":
        flash("Only a transfer that is in transit can be received.", "error")
        return redirect(list_url("pending"))
    receive_transfer(transfer, date.today())
    transfer.status = "Received"
    transfer.received_by_id = auth_service.actor_id()               # W1: kisne receive kiya
    db.session.commit()
    flash(f"{transfer.transfer_no} received: the goods are now in {transfer.to_warehouse.name}.", "success")
    return redirect(list_url("completed"))


@stock_transfers_bp.route("/stock_transfers/cancel/<int:transfer_id>", methods=["POST"])
def stock_transfers_cancel(transfer_id):
    transfer = StockTransfer.query.filter_by(id=transfer_id, is_deleted=False).first_or_404()
    if transfer.status not in ("Draft", "In transit"):
        flash("This transfer cannot be cancelled.", "error")
        return redirect(list_url("completed"))
    was_in_transit = transfer.status == "In transit"
    if was_in_transit:
        transfer_cancelled(transfer)        # maal wapas source me (ulti rows)
    transfer.status = "Cancelled"
    transfer.cancelled_by_id = auth_service.actor_id()              # W1: kisne cancel kiya
    db.session.commit()
    flash(f"{transfer.transfer_no} cancelled." + (f" The goods went back to {transfer.from_warehouse.name}." if was_in_transit else ""), "success")
    return redirect(list_url("completed"))
