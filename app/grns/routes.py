from flask import render_template, Blueprint, redirect, url_for, request, flash, jsonify
from app.models import GRN, PurchaseOrder, GRNLine
from app.extensions import db
from datetime import datetime

grns_bp = Blueprint("grns", __name__, template_folder="templates")

@grns_bp.route('/grns')
def grns_list():
    grns = GRN.query.filter(GRN.is_deleted == False).order_by(GRN.id.desc()).all()
    total_count = len(grns)

    open_pos = PurchaseOrder.query.filter(
        PurchaseOrder.is_deleted == False,
        PurchaseOrder.status.in_(["Open", "Partial"])
    ).all()

    return render_template(
        "grns.html",
        active_nav='grns',
        grns=grns,
        total_count=total_count,
        result_count=total_count,
        open_pos=open_pos,
    )

@grns_bp.route('/grns/po_lines/<int:po_id>')
def grns_po_lines(po_id):
    po = PurchaseOrder.query.get_or_404(po_id)

    lines=[]
    for line in po.lines:
        prev_received =0
        for grn_line in GRNLine.query.filter_by(po_line_id=line.id).all():
            if grn_line.grn.status != "Draft":
                prev_received  += grn_line.received_qty

        lines.append(
            {
                "po_line_id": line.id,
                "material_code": line.raw_material.code if line.raw_material else "",
                "material_name": line.raw_material.name if line.raw_material else "",
                "po_qty": line.ordered_qty,
                "prev_received": prev_received,
                "unit_code": line.unit.code if line.unit else "",
            }
        )    
    return jsonify(vendor=po.vendor.name if po.vendor else "", lines=lines)

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
        is_deleted=False,
    )
    db.session.add(grn)
    db.session.flush()

    i=0
    while True:
        po_line_id_raw = (request.form.get(f'po_line_id_{i}') or "").strip()
        received_qty_raw = (request.form.get(f'received_qty_{i}') or "").strip()
        batch_raw = (request.form.get(f'batch_lot_no_{i}') or "").strip()
        mfg_raw = (request.form.get(f'mfg_date_{i}') or "").strip()

        if not po_line_id_raw:
            break

        if received_qty_raw and batch_raw:
            db.session.add(GRNLine(
                grn_id=grn.id,
                po_line_id=int(po_line_id_raw),
                received_qty=float(received_qty_raw),
                batch_lot_no=batch_raw,
                mfg_date=datetime.strptime(mfg_raw, "%Y-%m-%d").date() if mfg_raw else None,

            ))    
        i += 1

    db.session.commit()
    flash(f"GRN {grn_no} saved as {status}.", "success")
    return redirect(url_for('grns.grns_list'))        

@grns_bp.route('/grns/post/<int:grn_id>', methods=['POST'])
def grns_post(grn_id):
    grn = GRN.query.get_or_404(grn_id)

    if grn.status != "Draft":
        return redirect(url_for('grns.grns_list'))

    grn.status = "Pending QC"
    db.session.commit()
    flash(f"GRN {grn.grn_no} posted — now Pending QC.", "success")
    return redirect(url_for('grns.grns_list'))