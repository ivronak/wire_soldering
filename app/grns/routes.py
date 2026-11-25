from flask import render_template, Blueprint, redirect, url_for, request, flash, jsonify
from app.inventory.posting import receive_grn, store_warehouse_for, InventoryError
from app.models import GRN, PurchaseOrder, GRNLine, Rack
from app.extensions import db
from app.auth import service as auth_service
from datetime import datetime

grns_bp = Blueprint("grns", __name__, template_folder="templates")


def store_racks_for(po):
    # PO ke store (RM) warehouse ke chalu racks — QC pass ke baad maal isi warehouse me jaata hai, isliye rack bhi isi ke.
    # Store warehouse na ho to khaali list (rack optional hai, GRN phir bhi ban sakti hai).
    try:
        store = store_warehouse_for(po)
    except InventoryError:
        return []
    return Rack.query.filter_by(warehouse_id=store.id, is_active=True, is_deleted=False).order_by(Rack.name).all()

def refresh_po_status(po):
    if po.status in ("Draft", "Cancelled"):
        return

    # Har line ko ALAG dekhte hain: pehle sab lines ka total jodte the, par KG aur PCS jaise alag units jod dene se
    # (aur ek line ke over-receipt se doosri line ki kami chhup jaane se) PO "Closed" ho jaata tha jabki ek line baaki thi,
    # aur phir uski GRN bhi nahi ban paati thi.
    any_received = False
    all_complete = True
    for line in po.lines:
        if line.received_qty > 0:
            any_received = True
        if line.received_qty < line.ordered_qty:
            all_complete = False

    if not any_received:
        po.status = "Open"
    elif all_complete:
        po.status = "Closed"
    else:
        po.status = "Partial"

@grns_bp.route('/grns')
def grns_list():
    # §10.6 + auto-flow: "New GRN" button nahi hai — kaam pichle step (PO confirm) se khud yahan aata hai.
    # GRN step ka kaam = maal receive karke GRN post karna. Isliye:
    #   pending   = (1) confirm ho chuke PO jinka maal aana baaki (Open/Partial) → row pe "Receive goods"
    #               (2) Draft GRN (save hui, post baaki) → row pe "Post GRN"
    #   completed = post ho chuki GRN (Pending QC / Partial QC / Closed) — ab unka agla kaam QC page pe hai
    tab = (request.args.get("tab") or "pending").strip().lower()
    if tab != "completed":
        tab = "pending"  # ?tab=kuchbhi aaye to bhi pending

    open_pos = PurchaseOrder.query.filter(
        PurchaseOrder.is_deleted == False,
        PurchaseOrder.status.in_(["Open", "Partial"])
    ).order_by(PurchaseOrder.id.desc()).all()

    base = GRN.query.filter(GRN.is_deleted == False)
    draft_grns = base.filter(GRN.status == "Draft").order_by(GRN.id.desc()).all()
    posted_grns = base.filter(GRN.status != "Draft").order_by(GRN.id.desc()).all()
    # F3: PO-wise grouping — ek PO ke GRN saath-saath (naya PO pehle, PO ke andar naya GRN pehle)
    draft_grns.sort(key=lambda grn: (-grn.po_id, -grn.id))

    # Pending tab ek hi list: har PO ke neeche pehle uski "maal aana baaki" row, phir uske Draft GRN (F3: PO-wise group)
    pending_items = []
    for po in open_pos:
        pending_items.append({"kind": "po", "po": po, "po_id": po.id, "grn": None, "order": 0, "gid": 0})
    for grn in draft_grns:
        pending_items.append({"kind": "draft", "po": grn.po, "po_id": grn.po_id, "grn": grn, "order": 1, "gid": grn.id})
    pending_items.sort(key=lambda item: (-item["po_id"], item["order"], -item["gid"]))
    posted_grns.sort(key=lambda grn: (-grn.po_id, -grn.id))

    pending_count = len(open_pos) + len(draft_grns)
    completed_count = len(posted_grns)
    total_count = pending_count if tab == "pending" else completed_count

    return render_template(
        "grns.html",
        active_nav='grns',
        grns=posted_grns,
        draft_grns=draft_grns,
        pending_items=pending_items,
        open_pos=open_pos,
        tab=tab,
        pending_count=pending_count,
        completed_count=completed_count,
        total_count=total_count,
        result_count=total_count,
    )

@grns_bp.route('/grns/po_lines/<int:po_id>')
def grns_po_lines(po_id):
    po = PurchaseOrder.query.get_or_404(po_id)

    lines=[]
    for line in po.lines:
        lines.append(
            {
                "po_line_id": line.id,
                "material_code": line.raw_material.code if line.raw_material else "",
                "material_name": line.raw_material.name if line.raw_material else "",
                "po_qty": line.ordered_qty,
                "prev_received": line.received_qty,
                "remaining": line.remaining_qty,
                "unit_code": line.unit.code if line.unit else "",
            }
        )    
    racks = [{"id": rack.id, "name": rack.name} for rack in store_racks_for(po)]
    return jsonify(vendor=po.vendor.name if po.vendor else "", lines=lines, racks=racks)

@grns_bp.route('/grns/add', methods=['POST'])
def grns_add():
    po_id = int(request.form.get('po_id')) if (request.form.get('po_id') or "").strip() else None
    grn_date_raw = (request.form.get('grn_date') or "").strip()
    challan_no = (request.form.get('challan_no') or "").strip()
    transporter = (request.form.get('transporter') or "").strip()
    vehicle_no = (request.form.get('vehicle_no') or "").strip()
    gross_weight = float(request.form.get('gross_weight')) if (request.form.get('gross_weight') or "").strip() else None
    remarks = (request.form.get('remarks') or "").strip()
    grn_action = (request.form.get('grn_action') or "post").strip()

    if not po_id or not grn_date_raw:
        return redirect(url_for('grns.grns_list'))

    # PO pehle hi check karo — galat id pe pehle refresh_po_status(None) crash karta tha.
    # Sirf Open/Partial PO pe GRN ban sakti hai (dropdown bhi yahi dikhata hai, lekin backend pe bhi rokna zaroori)
    po = PurchaseOrder.query.get(po_id)
    if not po or po.is_deleted or po.status not in ("Open", "Partial"):
        flash("This purchase order is not open for receiving.", "error")
        return redirect(url_for('grns.grns_list'))

    # Is PO ki apni lines ke id — form me kisi aur PO ki line aaye to reject
    valid_line_ids = {line.id for line in po.lines}
    # Rack sirf PO ke store warehouse ke chalu racks me se (frontend ki list pe bharosa nahi, backend pe bhi jaanch)
    valid_rack_ids = {rack.id for rack in store_racks_for(po)}

    grn_date = datetime.strptime(grn_date_raw, "%Y-%m-%d").date()

    year = grn_date.year
    count = GRN.query.filter(GRN.grn_no.like(f"GRN-{year}-%")).count()
    grn_no = f"GRN-{year}-{count + 1:03d}"

    status = "Draft" if grn_action == "draft" else "Pending QC"

    grn = GRN(
        grn_no=grn_no,
        po_id=po_id,
        grn_date=grn_date,
        challan_no=challan_no,
        transporter=transporter,
        vehicle_no=vehicle_no,
        gross_weight=gross_weight,
        status=status,
        remarks=remarks,
        created_by_id=auth_service.actor_id(),       # W1: kisne banayi
        posted_by_id=auth_service.actor_id() if status != "Draft" else None,   # seedha post kiya to wahi post karne wala
        is_deleted=False,
    )
    db.session.add(grn)
    db.session.flush()

    i=0
    lines_added = 0
    while True:
        po_line_id_raw = (request.form.get(f'po_line_id_{i}') or "").strip()
        received_qty_raw = (request.form.get(f'received_qty_{i}') or "").strip()
        batch_raw = (request.form.get(f'batch_lot_no_{i}') or "").strip()
        mfg_raw = (request.form.get(f'mfg_date_{i}') or "").strip()
        rack_raw = (request.form.get(f'rack_id_{i}') or "").strip()

        if not po_line_id_raw:
            break

        try:
            qty_is_zero = bool(received_qty_raw) and float(received_qty_raw) == 0
        except ValueError:
            qty_is_zero = False
        if qty_is_zero and not batch_raw:
            received_qty_raw = ""                     # 0 qty aur batch khaali = is line me kuch nahi aaya, chhod do
        if bool(received_qty_raw) != bool(batch_raw):
            db.session.rollback()
            flash("For each line you receive, enter both the quantity and the vendor batch / lot, or leave the line empty.", "error")
            return redirect(url_for('grns.grns_list'))
        if received_qty_raw and batch_raw:
            po_line_id = int(po_line_id_raw)
            received_qty = float(received_qty_raw)

            # Line isi PO ki honi chahiye, aur qty 0 se zyada.
            # Note: ordered qty se zyada aana (over-receipt) jaan-boojhkar allowed hai —
            # form pe sirf warning popup aata hai, PO View me "X over the ordered qty" dikhta hai (§10.7 decision)
            if po_line_id not in valid_line_ids or received_qty <= 0:
                db.session.rollback()
                flash("Each received qty must be more than 0 and belong to this purchase order.", "error")
                return redirect(url_for('grns.grns_list'))

            rack_id = int(rack_raw) if rack_raw.isdigit() else None
            if rack_id is not None and rack_id not in valid_rack_ids:
                db.session.rollback()
                flash("Choose a rack that belongs to the store warehouse of this purchase order.", "error")
                return redirect(url_for('grns.grns_list'))

            db.session.add(GRNLine(
                grn_id=grn.id,
                po_line_id=po_line_id,
                received_qty=received_qty,
                batch_lot_no=batch_raw,
                mfg_date=datetime.strptime(mfg_raw, "%Y-%m-%d").date() if mfg_raw else None,
                rack_id=rack_id,
            ))
            lines_added += 1
        i += 1

    # Bina kisi line ke khaali GRN save mat karo
    if lines_added == 0:
        db.session.rollback()
        flash("Enter received qty and batch / lot no. for at least one line.", "error")
        return redirect(url_for('grns.grns_list'))

    refresh_po_status(po)

    # Post hui GRN (Draft nahi) ka maal turant stock me: QC Hold warehouse me (app/inventory/posting.py)
    if status != "Draft":
        try:
            db.session.flush()
            receive_grn(grn)
        except InventoryError as error:
            db.session.rollback()
            flash(str(error), "error")
            return redirect(url_for('grns.grns_list'))

    db.session.commit()
    # Post hui GRN completed tab me chali jaati hai — batao ki agla kaam (QC) kahan hai
    if status == "Draft":
        flash(f"GRN {grn_no} saved as Draft — post it from the Pending list when ready.", "success")
    else:
        flash(f"GRN {grn_no} posted — its lots are now waiting on the Inward QC page.", "success")
    return redirect(url_for('grns.grns_list'))        

@grns_bp.route('/grns/post/<int:grn_id>', methods=['POST'])
def grns_post(grn_id):
    grn = GRN.query.get_or_404(grn_id)

    if grn.status != "Draft":
        return redirect(url_for('grns.grns_list'))

    grn.status = "Pending QC"
    grn.posted_by_id = auth_service.actor_id()          # W1: kisne post kiya
    refresh_po_status(grn.po)
    try:
        receive_grn(grn)
    except InventoryError as error:
        db.session.rollback()
        flash(str(error), "error")
        return redirect(url_for('grns.grns_list'))
    db.session.commit()
    flash(f"GRN {grn.grn_no} posted — its lots are now waiting on the Inward QC page.", "success")
    return redirect(url_for('grns.grns_list'))