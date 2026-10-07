import _guard  # asli erp.db pe chalti hai — bina ERP_ALLOW_DB_SCRIPTS=1 ke ruk jaayegi, aur pehle backup banegi

from app import app
from app.extensions import db
from app.models import InwardQC, RejectionMemo

with app.app_context():
    # 1) Purana naam naye format me: Memo-2026-001 -> MEMO-2026-001
    #    Sirf "Memo-" se shuru hone wale — dobara chalaane par kuch nahi badlega
    for memo in RejectionMemo.query.all():
        if memo.memo_no.startswith("Memo-"):
            memo.memo_no = "MEMO-" + memo.memo_no[len("Memo-"):]
    db.session.flush()   # naye naam DB me bhejo, taaki neeche ki ginti unhe dekh sake

    # 2) Jin final QC (Failed / Partial) me reject qty hai par memo nahi bana, unka memo banao
    missing = InwardQC.query.filter(
        InwardQC.is_deleted == False,
        InwardQC.status.in_(["Failed", "Partial"]),
        InwardQC.rejected_qty > 0,
    ).order_by(InwardQC.id).all()

    for qc in missing:
        if qc.memo is not None:
            continue   # is QC ka memo pehle se hai — chhod do
        year = qc.inspection_date.year
        count = RejectionMemo.query.filter(RejectionMemo.memo_no.like(f"MEMO-{year}-%")).count()
        db.session.add(RejectionMemo(
            memo_no=f"MEMO-{year}-{count + 1:03d}",
            inward_qc_id=qc.id,
            memo_date=qc.inspection_date,
            rejected_qty=qc.rejected_qty,
            reason=qc.remarks or None,
        ))
        db.session.flush()   # agle QC ki ginti me yeh memo bhi gine
        print("Memo created for", qc.qc_no)

    db.session.commit()

    for memo in RejectionMemo.query.order_by(RejectionMemo.id).all():
        print(memo.memo_no, "->", memo.inward_qc.qc_no, "| qty", memo.rejected_qty)