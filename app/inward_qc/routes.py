import os

from flask import render_template, Blueprint, redirect, url_for, request, flash, jsonify, current_app, send_from_directory
from werkzeug.utils import secure_filename
from app.models import InwardQC, GRN, GRNLine, RejectionMemo, RMQCParameter, InwardQCResult
from app.raw_materials.routes import qc_parameter_to_dict
from app.extensions import db
from datetime import datetime

inward_qc_bp = Blueprint("inward_qc", __name__, template_folder="templates")

# F11: QC report / certificate ki file. PO invoice upload jaisa pattern: sirf PDF / PNG / JPG, 5 MB tak.
ALLOWED_REPORT_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}
MAX_REPORT_BYTES = 5 * 1024 * 1024


def check_report_file(report):
    # Wapas: error message (galat ho to) ya None (theek hai / file di hi nahi)
    if report is None or not report.filename:
        return None
    ext = report.filename.rsplit(".", 1)[1].lower() if "." in report.filename else ""
    if ext not in ALLOWED_REPORT_EXTENSIONS:
        return "QC report must be a PDF, PNG or JPG file."
    report.stream.seek(0, os.SEEK_END)
    size = report.stream.tell()
    report.stream.seek(0)
    if size > MAX_REPORT_BYTES:
        return "The QC report file is too large (maximum 5 MB)."
    return None


def final_qc_line_ids():
    # Jin GRN lines ka final (non-Draft) QC ho chuka — unka kaam khatam, dobara inspect nahi hongi
    rows = InwardQC.query.filter(InwardQC.is_deleted == False, InwardQC.status != "Draft").all()
    return {q.grn_line_id for q in rows}

def latest_draft_payload(line_id):
    # Is lot ka sabse naya Draft QC (agar hai) — Inspect form me values wapas bharne ke liye JSON dictionary.
    # "answers" = {parameter id (text): number ya "pass"/"fail"} — form ke actual_N / result_N me wapas jaane ke liye.
    d = InwardQC.query.filter_by(grn_line_id=line_id, status="Draft", is_deleted=False).order_by(InwardQC.id.desc()).first()
    if not d:
        return None
    answers = {}
    for r in d.results:
        if r.parameter_id is None:
            continue
        if r.check_type == "pass_fail":
            answers[str(r.parameter_id)] = "pass" if r.passed else "fail"
        else:
            answers[str(r.parameter_id)] = r.actual_value
    return {
        "qc_no": d.qc_no,
        "inspection_date": d.inspection_date.strftime("%Y-%m-%d") if d.inspection_date else "",
        "inspector": d.inspector or "",
        "sample_size": d.sample_size,
        "passed_qty": d.passed_qty,
        "rejected_qty": d.rejected_qty,
        "remarks": d.remarks or "",
        "answers": answers,
    }

def read_qc_results(grn_line, is_final):
    # Form se parameter-wise results padho aur check karo. Wapas: (rows, None) ya (None, "error message").
    # rows = [{"parameter": RMQCParameter, "actual_value": float ya None, "passed": True/False}, ...]
    rm = grn_line.po_line.raw_material if grn_line.po_line else None
    if not rm:
        return [], None

    # Is material ke abhi ke active parameters. Browser ki list par bharosa nahi, DB se khud lete hain.
    allowed = {
        p.id : p for p in RMQCParameter.query.filter_by(raw_material_id=rm.id, is_deleted=False, is_active=True).all()
    }

    rows =[]
    seen=set()
    i=0
    while True:

        param_id = request.form.get(f'param_id_{i}', type=int)
        if param_id is None:
            break

        p = allowed.get(param_id)    
        if p is None or param_id in seen:
            return None, "Invalid QC parameter in the form. Please reopen the inspection."
        seen.add(param_id)

        if p.check_type == "pass_fail":
            answer = request.form.get(f"result_{i}")
            actual_value = None
            if answer == "pass":
                passed = True
            elif answer == "fail":
                passed = False
            else:
                passed = None   # abhi kuch chuna nahi  

        else:
            actual_value = request.form.get(f'actual_{i}', type=float)
            if actual_value is None:
                passed = None
            else:
                passed = (
                    (p.min_value is None or actual_value >= p.min_value)
                    and(p.max_value is None or actual_value <= p.max_value )
                ) 

        if passed is not None:
            rows.append({"parameter":p, "actual_value":actual_value, "passed":passed})
        i+=1

    if is_final:
        done_ids = {r["parameter"].id for r in rows}
        missing = [p.name for pid, p in allowed.items() if pid not in done_ids]
        if missing:
            return None, "Enter a result for every QC parameter: " + ", ".join(missing) + "."

    return rows, None        
                   

@inward_qc_bp.route('/inward_qc')
def inward_qc_list():
    # §10.6: ?tab=pending (default) / ?tab=completed
    # QC me "pending" = woh GRN lines jinka inspection abhi baaki hai (QC record ho ya na ho),
    # "completed" = final QC records (Passed / Partial / Failed)
    tab = (request.args.get("tab") or "pending").strip().lower()
    if tab != "completed":
        tab = "pending"

    # Sirf wahi GRN jinka QC baaki hai — "Closed" GRN (saari lines ka QC ho chuka) dropdown me nahi aani chahiye
    pending_grns = GRN.query.filter(
        GRN.status.in_(["Pending QC", "Partial QC"]),
        GRN.is_deleted == False,
    ).order_by(GRN.id.desc()).all()

    done_ids = final_qc_line_ids()

    # Draft QC (adhoora save) — line id -> sabse naya draft (order id se, baad wala purane ko overwrite karta hai)
    drafts = {}
    for q in InwardQC.query.filter(InwardQC.is_deleted == False, InwardQC.status == "Draft").order_by(InwardQC.id).all():
        drafts[q.grn_line_id] = q

    # Pending queue: har pending GRN ki woh lines jinka final QC nahi hua
    awaiting = []
    for g in pending_grns:
        for line in g.lines:
            if line.id not in done_ids:
                awaiting.append({"grn": g, "line": line, "draft": drafts.get(line.id)})

    completed = InwardQC.query.filter(
        InwardQC.is_deleted == False,
        InwardQC.status != "Draft",
    ).order_by(InwardQC.id.desc()).all()

    # F3: PO-wise grouping — ek PO ke lots / QC saath-saath (naya PO pehle)
    awaiting.sort(key=lambda a: (-a["grn"].po_id, -a["grn"].id, a["line"].id))
    completed.sort(key=lambda qc: (-(qc.grn_line.grn.po_id if qc.grn_line and qc.grn_line.grn else 0), -qc.id))

    return render_template(
        "inwards_qc.html",
        tab=tab,
        awaiting=awaiting,
        inwards=completed,
        pending_count=len(awaiting),
        completed_count=len(completed),
        pending_grns=pending_grns,
        active_nav="inwards_qc",
    )

@inward_qc_bp.route('/inward_qc/grn_lines/<int:grn_id>')
def inward_qc_grn_lines(grn_id):
    grn = GRN.query.get_or_404(grn_id)
    done_ids = final_qc_line_ids()
    lines=[]
    for line in grn.lines:
        # Jis line ka final QC ho chuka wo dropdown me mat dikhao (backend waise bhi dobara final QC rokta hai)
        if line.id in done_ids:
            continue
        rm = line.po_line.raw_material if line.po_line else None
        params = []
        if rm:
            params=RMQCParameter.query.filter_by(raw_material_id=rm.id, is_deleted=False, is_active=True).order_by(RMQCParameter.sort_order, RMQCParameter.id).all()
        lines.append({
            "id":line.id,
            "material_code":rm.code if rm else "",
            "material_name":rm.name if rm else "",
            "batch_lot_no":line.batch_lot_no or "",
            "received_qty":line.received_qty,
            "parameters": [qc_parameter_to_dict(p) for p in params],
            # Is lot ka adhoora draft (agar hai) — form me wapas bharne ke liye, warna None
            "draft": latest_draft_payload(line.id),
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

    # GRN line ko DB se khud load karo — baad me inward_qc.grn_line pe depend nahi karna,
    # kyunki naya (abhi save nahi hua) object apna relationship None deta hai (wahi purana crash tha)
    grn_line = GRNLine.query.get(grn_line_id)
    if not grn_line or grn_line.grn.is_deleted:
        flash("Selected GRN line was not found.", "error")
        return redirect(url_for('inward_qc.inward_qc_list'))

    # Backend validation — sirf HTML ke min="0" pe bharosa nahi (CLAUDE.md §5 rule 4)
    if passed_qty < 0 or rejected_qty < 0:
        flash("Passed and rejected qty cannot be negative.", "error")
        return redirect(url_for('inward_qc.inward_qc_list'))

    # Jitna maal aaya usse zyada pass + reject nahi ho sakta
    if passed_qty + rejected_qty > grn_line.received_qty:
        flash(f"Passed + rejected qty cannot be more than the received qty ({grn_line.received_qty}).", "error")
        return redirect(url_for('inward_qc.inward_qc_list'))

    if qc_action != "draft":
        # Final result me kuch to qty honi chahiye — 0 pass + 0 reject ko "Passed" mat bana do
        if passed_qty + rejected_qty <= 0:
            flash("Enter passed or rejected qty before submitting the result.", "error")
            return redirect(url_for('inward_qc.inward_qc_list'))

        # Ek GRN line ka final QC ek hi baar — warna passed qty do baar ginegi (aage Purchase Invoice me galat billing)
        already_final = InwardQC.query.filter(
            InwardQC.grn_line_id == grn_line_id,
            InwardQC.is_deleted == False,
            InwardQC.status != "Draft",
        ).first()
        if already_final:
            flash(f"This material / lot already has a final QC result ({already_final.qc_no}).", "error")
            return redirect(url_for('inward_qc.inward_qc_list'))

    result_rows, error = read_qc_results(grn_line, is_final=(qc_action != 'draft'))
    if error:
        flash(error,"error")
        return redirect(url_for('inward_qc.inward_qc_list'))

    # QC report file (optional): galat file ho to kuch bhi save hone se pehle yahin ruk jao
    report = request.files.get("report_file")
    report_error = check_report_file(report)
    if report_error:
        flash(report_error, "error")
        return redirect(url_for('inward_qc.inward_qc_list'))

    # Sab checks pass ho gaye. Draft = "kaam chalu hai", isliye naya save (draft ya final) is lot ke purane draft ko
    # replace karta hai (purana hide ho jata hai) — warna har draft save par ek aur draft jama hota jata.
    # Ye checks ke BAAD isliye ki galti hone par purana draft na ud jaye.
    inherited_report = None            # naya file nahi diya to purane draft ki file saath chale
    for old_draft in InwardQC.query.filter_by(grn_line_id=grn_line_id, status="Draft", is_deleted=False).all():
        old_draft.is_deleted = True
        if old_draft.report_file:
            inherited_report = old_draft.report_file

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
    db.session.flush()                 # id chahiye: file ka folder QC id se banta hai

    if report is not None and report.filename:
        ext = report.filename.rsplit(".", 1)[1].lower()
        safe_name = secure_filename(report.filename) or ("report." + ext)
        folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'inward_qc', str(inward_qc.id))
        os.makedirs(folder, exist_ok=True)
        report.save(os.path.join(folder, safe_name))
        inward_qc.report_file = 'inward_qc/' + str(inward_qc.id) + '/' + safe_name      # DB me hamesha "/" (Windows ka \ nahi)
    else:
        inward_qc.report_file = inherited_report

    saved_results=[]
    for row in result_rows:
        p = row["parameter"]
        result=InwardQCResult(
            inward_qc=inward_qc,
            parameter_id=p.id,
            parameter_name=p.name,
            unit_label=p.unit_label,
            check_type=p.check_type,
            min_value=p.min_value,
            max_value=p.max_value,
            actual_value=row['actual_value'],
            passed=row['passed'],
        )
        db.session.add(result)
        saved_results.append(result)

    # §6.5 Rejection memo: final result me rejected qty ho (Failed / Partial) to memo apne aap bane.
    # Draft me nahi — draft abhi pakka result nahi hai. Alag "New memo" button bhi nahi (auto-flow rule).
    memo_no = None
    if status != "Draft" and rejected_qty > 0:
        db.session.flush()

        reason_parts =[]
        failed_texts = [r.fail_text for r in saved_results if not r.passed]
        if failed_texts:
            reason_parts.append("Failed tests: "+"; ".join(failed_texts))
        if remarks:
            reason_parts.append(remarks)
        reason = " | ".join(reason_parts)[:255] or None
    


        memo_count = RejectionMemo.query.filter(RejectionMemo.memo_no.like(f"MEMO-{year}-%")).count()
        memo_no = f"MEMO-{year}-{memo_count + 1:03d}"
        db.session.add(RejectionMemo(
            memo_no = memo_no,
            inward_qc_id = inward_qc.id,
            memo_date = inspection_date,
            rejected_qty = rejected_qty,
            reason = reason,
        ))    


    # Sirf final result pe GRN badlo — Draft pe mat chhedo
    if status != "Draft":
        # Upar load kiya hua grn_line use karo (inward_qc.grn_line abhi None hoga — save nahi hua)
        grn = grn_line.grn
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
    if status == "Draft":
        flash(f"Inward QC {qc_no} saved as Draft — the lot stays in the Pending list until you submit a result.", "success")
    else:
        message = f"Inward QC {qc_no} saved as {status}."
        if memo_no:
            message += f" Rejection memo {memo_no} was raised."
        flash(message, "success")
    return redirect(url_for('inward_qc.inward_qc_list'))        


@inward_qc_bp.route('/inward_qc/<int:qc_id>/report')
def inward_qc_report(qc_id):
    # QC report / certificate ki file kholna (View panel ka link)
    qc = InwardQC.query.get_or_404(qc_id)
    if not qc.report_file or qc.is_deleted:
        return redirect(url_for('inward_qc.inward_qc_list'))
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], qc.report_file)
