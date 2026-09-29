from flask import render_template, Blueprint, redirect, url_for, request, flash, jsonify
from app.models import InwardQC, GRN
from app.extensions import db
from datetime import datetime

inward_qc_bp = Blueprint("inward_qc", __name__, template_folder="templates")

@inward_qc_bp.route('/inward_qc')
def inward_qc_list():
    inwards = InwardQC.query.filter(InwardQC.is_deleted == False).order_by(InwardQC.id.desc()).all()
    pending_grns = GRN.query.filter(GRN.status != "Draft", GRN.is_deleted == False).all()

    return render_template(
        "inwards_qc.html",
        inwards=inwards,
        pending_grns=pending_grns,
        active_nav="inwards_qc",
    )

@inward_qc_bp.route('/inward_qc/grn_lines/<int:grn_id>')
def inward_qc_grn_lines(grn_id):
    grn = GRN.query.get_or_404(grn_id)
    lines=[]
    for line in grn.lines:
        rm = line.po_line.raw_material if line.po_line else None
        lines.append({
            "id":line.id,
            "material_code":rm.code if rm else "",
            "material_name":rm.name if rm else "",
            "batch_lot_no":line.batch_lot_no or "",
            "received_qty":line.received_qty,
        })
    return jsonify(lines=lines)    

@inward_qc_bp.route('/inward_qc/add', methods=['POST'])
def inward_qc_add():
    inspection_date_raw = (request.form.get('inspection_date') or "").strip()
    inspector = (request.form.get('inspector') or "").strip()
    grn_line_id = int(request.form.get('grn_line_id')) if (request.form.get('grn_line_id') or "").strip() else None
    sample_size = float(request.form.get('sample_size') or 0) 
    passed_qty = float(request.form.get('passed_qty') or 0) 
    rejected_qty = float(request.form.get('rejected_qty') or 0) 
    remarks = (request.form.get('remarks') or "").strip()
    qc_action = (request.form.get("qc_action") or "draft").strip()


    if not inspection_date_raw or not grn_line_id :
        return redirect(url_for('inward_qc.inward_qc_list'))

    inspection_date = datetime.strptime(inspection_date_raw, "%Y-%m-%d").date()

    year=inspection_date.year
    count=InwardQC.query.filter(InwardQC.qc_no.like(f"QC-{year}-%")).count()
    qc_no=f"QC-{year}-{count + 1:03d}"

    if qc_action == "draft":
        status = "Draft"
    elif rejected_qty ==0:
        status = "Passed"
    elif passed_qty == 0:
        status = "Failed"
    else:
        status = "Partial"

    inward_qc = InwardQC(
        qc_no=qc_no,
        grn_line_id=grn_line_id,
        inspection_date=inspection_date,
        inspector=inspector,
        sample_size=sample_size,
        passed_qty=passed_qty,
        rejected_qty=rejected_qty,
        status=status,
        remarks=remarks,
        is_deleted=False,
    )            

    db.session.add(inward_qc)

    # Sirf final result pe GRN badlo — Draft pe mat chhedo
    if status != "Draft":
        grn = inward_qc.grn_line.grn
        total = len(grn.lines)
        done = 0
        for line in grn.lines:
            has_final = InwardQC.query.filter(
                InwardQC.grn_line_id == line.id,
                InwardQC.is_deleted == False,
                InwardQC.status != "Draft",
            ).first()
            if has_final:
                done += 1
        if done == 0:
            grn.status = "Pending QC"
        elif done < total:
            grn.status = "Partial QC"
        else:
            grn.status = "Closed"

    db.session.commit()
    flash(f"Inward_QC {qc_no} saved as {status}.", "success")
    return redirect(url_for('inward_qc.inward_qc_list'))        