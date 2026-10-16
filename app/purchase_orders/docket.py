# Procurement docket ka data: ek PO se shuru karke uske saare documents ek jagah jama karta hai.
#   PO -> GRN -> lot (GRN line) -> QC (+ test results, + rejection memo)
#   lot -> bill (purchase invoice) -> return (purchase return)
#
# Ye file sirf PADHTI hai: koi db.session.add / commit nahi, koi ledger ya stock ka asar nahi.
# Jinja template (purchase_order_docket.html) isi se bani plain dictionaries / lists dikhata hai.
#
# Dhyan: PurchaseInvoice me po_id nahi hota (bill vendor ka hota hai aur kai POs ke lots mila sakta hai),
# isliye bill lots ke raaste dhoondte hain, aur ek bill ko sirf ek hi baar dikhate hain.
# Mixed bill par is PO ki lines hi dikhate hain (baaki PO ki lines ka isse koi lena-dena nahi).
#
# Status ke naam: DB me stored status ("Partial", "Closed"...) alag-alag documents me ek hi shabd the aur
# confuse karte the. Docket me label quantities se nikalte hain (jaise "40 of 50 passed"), stored status se nahi.


# ---------------------------------------------------------------- dikhane ke helpers (template ke filters)

def format_qty(value):
    # Quantity padhne layak: 50.0 -> "50", 1234567.5 -> "1,234,567.5". (Python ka %g 1e+06 jaisa likh deta hai, isliye ye)
    try:
        text = "{:,.4f}".format(float(value or 0))
    except (TypeError, ValueError):
        return "0"
    text = text.rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def format_rate(value):
    # Rate: kam se kam 2 decimal, zyada ho to 4 tak (12.3456 ko 12.35 nahi dikhana, warna hisaab nahi milta)
    try:
        text = "{:,.4f}".format(float(value or 0))
    except (TypeError, ValueError):
        return "0.00"
    whole, frac = text.split(".")
    frac = frac.rstrip("0")
    if len(frac) < 2:
        frac = frac.ljust(2, "0")
    return whole + "." + frac


def format_reading(value):
    # Lab ka naapa hua number: 8 decimal tak, bekar zero hata ke (99.49999 ko 99.5 nahi dikhana, wo limit jaisa lagta)
    try:
        text = "{:,.8f}".format(float(value))
    except (TypeError, ValueError):
        return "—"
    text = text.rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def format_inr(value):
    # Paise ko Indian tareeke se: 595900 -> "5,95,900.00" (Invoice / Return pages bhi aise hi dikhate hain)
    try:
        amount = round(float(value or 0), 2)
    except (TypeError, ValueError):
        amount = 0.0
    sign = "-" if amount < 0 else ""
    whole, frac = "{:.2f}".format(abs(amount)).split(".")
    if len(whole) > 3:
        head = whole[:-3]
        tail = whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups) + "," + tail
    return sign + whole + "." + frac


# ---------------------------------------------------------------- andar ke chhote helpers

def _po_id_of(invoice_line):
    # Bill ki line kis PO ki hai: bill line -> lot (GRN line) -> GRN -> PO.
    # (Return line ke liye uski invoice_line bhejo.)
    # Remove ki hui GRN ya toota hua link ho to None: aisi line ko "kisi aur ki" maante hain, taaki mixed note aaye.
    if invoice_line is None:
        return None
    grn_line = invoice_line.grn_line
    if grn_line is None or grn_line.grn is None or grn_line.grn.is_deleted:
        return None
    return grn_line.grn.po_id


def _unit_code(po_line):
    # PO line ki unit ka code (KG, PCS...); nahi mili to khaali
    if po_line is not None and po_line.unit is not None:
        return po_line.unit.code
    return ""


def _returned_qty(invoice_line):
    # Is bill line se kitna wapas gaya (Cancelled / remove kiye hue return nahi ginte).
    # Model ki property ki jagah yahin nikalte hain, taaki toota hua return row docket ko na tode.
    total = 0
    for return_line in invoice_line.return_lines:
        purchase_return = return_line.purchase_return
        if purchase_return is None or purchase_return.is_deleted or purchase_return.status == "Cancelled":
            continue
        total += return_line.qty or 0
    return total


def _line_value(line):
    # Bill / return line ki value GST ke saath (dono ki properties yahi naam rakhti hain)
    return round(line.taxable_amount + line.tax_amount, 2)


def _signed_charges(charge_lines):
    total = 0
    for charge_line in charge_lines:
        total += -charge_line.amount if charge_line.effect == "minus" else charge_line.amount
    return round(total, 2)


def _po_summary(po):
    # PO ki lines + total: PO print / PO View jaisa hi hisaab — PurchaseOrder.summary (app/tax.py) se, taaki ek PO ke do
    # alag total na dikhein. Line ka discount_percent PO print aur View me bhi nahi lagta, isliye yahan bhi nahi.
    summary = po.summary
    line_rows = []
    for line, tax_line in zip(po.lines, summary["lines"]):
        # Is PO line ka maal GRN-wise alag-alag: "GRN-001 ne 250, GRN-002 ne 250" — total ek number me nahi (client rule).
        # Draft GRN abhi post nahi hui, isliye nahi ginte (docket ke baaki hisson jaisa).
        receipts = []
        received_total = 0
        for grn_line in sorted(line.grn_lines, key=lambda gl: gl.id):
            grn = grn_line.grn
            if grn is None or grn.is_deleted or grn.status == "Draft":
                continue
            receipts.append({"grn_no": grn.grn_no, "grn_date": grn.grn_date, "created_at": grn.created_at,
                             "qty": grn_line.received_qty or 0})
            received_total += grn_line.received_qty or 0
        still_to_come = round((line.ordered_qty or 0) - received_total, 4)

        line_rows.append({
            "line": line,
            "unit": _unit_code(line),
            "amount": tax_line["value"],
            "tax_percent": tax_line["rate"],
            "receipts": receipts,
            "still_to_come": still_to_come if still_to_come > 0 else 0,
        })

    charge_rows = summary["charge_rows"]
    return {
        "lines": line_rows,
        "charges": charge_rows,
        "subtotal": summary["items_total"],
        "tax_total": summary["tax_total"],
        "charges_total": summary["charges_net"],
        "total": summary["grand_total"],
    }


def _qc_text(qc, received):
    # QC ka label quantities se: "40 of 50 passed", "All 50 passed", "All 50 rejected".
    # Stored status ("Partial", "Passed") se nahi, kyunki wo kam bataata hai aur kabhi galat lagta hai.
    passed = qc.passed_qty or 0
    rejected = qc.rejected_qty or 0
    if qc.status == "Failed":
        if received > 0 and rejected >= received:
            return "All " + format_qty(rejected) + " rejected", "p-red"
        return format_qty(rejected) + " of " + format_qty(received) + " rejected", "p-red"
    if received > 0 and passed >= received:
        return "All " + format_qty(passed) + " passed", "p-green"
    return format_qty(passed) + " of " + format_qty(received) + " passed", "p-amber"


def _po_state(po, quantity_rows):
    # PO ka label + ek saaf line: kitne items poore aaye, kya baaki hai. Quantities se nikalte hain (stored status se nahi:
    # wo alag-alag unit wali lines ko jod deta tha aur "Closed" dikha deta tha jabki ek line baaki thi).
    if po.status == "Draft":
        return {"label": "Draft", "pill": "p-grey", "sentence": "Draft: this PO is not confirmed yet."}
    if po.status == "Cancelled":
        sentence = "Closed early. The remaining quantity will not be delivered."
        if po.short_close_reason:
            sentence += " Reason: " + po.short_close_reason
        return {"label": "Short closed", "pill": "p-red", "sentence": sentence}

    lines = [row for row in quantity_rows if row["ordered"] > 0]
    if not lines:
        return {"label": po.status, "pill": "p-grey", "sentence": ""}

    complete = 0
    any_received = False
    pending = []
    for row in lines:
        if row["received"] > 0:
            any_received = True
        if row["left_to_receive"] <= 0:
            complete += 1
        else:
            name = row["line"].raw_material.name if row["line"].raw_material else "Item"
            pending.append(name + " " + format_qty(row["left_to_receive"]) + " " + row["unit"])

    if not any_received:
        return {"label": "Open, nothing received yet", "pill": "p-green", "sentence": "Nothing has been received yet."}
    if complete == len(lines):
        return {"label": "Fully received", "pill": "p-green", "sentence": "All items received."}
    return {
        "label": "Partly received",
        "pill": "p-amber",
        "sentence": "Partly received: " + str(complete) + " of " + str(len(lines)) + " items fully received. Still to come: " + ", ".join(pending) + ".",
    }


def build_docket(po):
    # Wapas: ek dictionary jisme PO ka poora chain hai (neeche return me keys dekho)

    # ---------- 1) GRN -> lots -> QC -> memo, aur saath me bills ke ids jama karte jao ----------
    grn_blocks = []
    invoices = []              # is PO ke lots par bane bills (ek bill ek hi baar)
    seen_invoice_ids = []
    totals_by_po_line = {}     # PO line id -> received / passed / rejected / billed / ... (quantity table ke liye)
    lot_count = 0
    draft_lot_count = 0
    qc_done_count = 0
    qc_pending_count = 0
    memo_count = 0
    draft_grn_count = 0

    for grn in sorted(po.grns, key=lambda g: g.id):
        if grn.is_deleted:
            continue                       # remove ki hui GRN docket me nahi aati
        is_draft = grn.status == "Draft"
        if is_draft:
            draft_grn_count += 1

        lot_rows = []
        lots_with_qc = 0
        for grn_line in sorted(grn.lines, key=lambda gl: gl.id):
            po_line = grn_line.po_line
            material = po_line.raw_material if po_line is not None else None

            # final_qc = Draft nahi, remove nahi wali QC; nahi hui to None ("Waiting for QC").
            # Draft GRN abhi post nahi hui, isliye uske lot par QC / bill kuch nahi dikhate (aisi state UI se banti hi nahi).
            qc = None
            memo = None
            results = []
            if not is_draft:
                qc = grn_line.final_qc
            if qc is not None:
                lots_with_qc += 1
                if qc.memo is not None and not qc.memo.is_deleted:
                    memo = qc.memo
                results = sorted(qc.results, key=lambda r: r.id)

            received = grn_line.received_qty or 0
            passed = (qc.passed_qty or 0) if qc is not None else 0
            rejected = (qc.rejected_qty or 0) if qc is not None else 0
            # QC ne jitna na pass kiya na reject kiya (received - passed - rejected): chhupna nahi chahiye
            undecided = round(received - passed - rejected, 4) if qc is not None else 0
            if undecided < 0.0001:
                undecided = 0
            qc_label = ""
            qc_pill = "p-grey"
            if qc is not None:
                qc_label, qc_pill = _qc_text(qc, received)

            # Is lot par bill / return: billed (Draft + Posted), usme se Draft kitna, aur active returns.
            # Sab yahin loop me nikalte hain (model ki properties nahi), taaki toota hua row docket ko na tode.
            billed = 0
            billed_draft = 0
            returned = 0
            if not is_draft:
                for invoice_line in grn_line.invoice_lines:
                    invoice = invoice_line.invoice
                    if invoice is None or invoice.is_deleted:
                        continue
                    # Bill ko ek hi baar jama karo (do lot ek hi bill me ho sakte hain); Cancelled bhi dikhate hain
                    if invoice.id not in seen_invoice_ids:
                        seen_invoice_ids.append(invoice.id)
                        invoices.append(invoice)
                    if invoice.status == "Cancelled":
                        continue           # Cancelled bill ki qty "billed" nahi ginti
                    billed += invoice_line.qty or 0
                    if invoice.status == "Draft":
                        billed_draft += invoice_line.qty or 0
                    returned += _returned_qty(invoice_line)
            billable = max(round(passed - billed, 4), 0)

            lot_count += 1
            if is_draft:
                draft_lot_count += 1
            else:
                if qc is None:
                    qc_pending_count += 1
                else:
                    qc_done_count += 1
            if memo is not None:
                memo_count += 1

            lot_rows.append({
                "line": grn_line,
                "material": material,
                "unit": _unit_code(po_line),
                "qc": qc,
                "qc_label": qc_label,
                "qc_pill": qc_pill,
                "memo": memo,
                "results": results,
                "undecided": undecided,
                "billed": round(billed, 4),
                "returned": round(returned, 4),
            })

            # PO line ke hisaab se jod (Draft GRN abhi "received" nahi ginti, PO page ki tarah)
            if po_line is not None and not is_draft:
                acc = totals_by_po_line.setdefault(po_line.id, {
                    "received": 0, "passed": 0, "rejected": 0, "billed": 0, "billed_draft": 0,
                    "billable": 0, "returned": 0, "lots": 0, "qc_lots": 0,
                })
                acc["received"] += received
                acc["passed"] += passed
                acc["rejected"] += rejected
                acc["billed"] += billed
                acc["billed_draft"] += billed_draft
                acc["billable"] += billable
                acc["returned"] += returned
                acc["lots"] += 1
                if qc is not None:
                    acc["qc_lots"] += 1

        # GRN ka label lots ki asli QC sthiti se (stored status se nahi)
        if is_draft:
            grn_label, grn_pill = "Draft, not posted", "p-grey"
        elif lots_with_qc == 0:
            grn_label, grn_pill = "Waiting for QC", "p-amber"
        elif lots_with_qc == len(lot_rows):
            grn_label, grn_pill = "QC done", "p-green"
        else:
            grn_label, grn_pill = "QC done for " + str(lots_with_qc) + " of " + str(len(lot_rows)) + " lots", "p-amber"

        grn_blocks.append({"grn": grn, "lots": lot_rows, "label": grn_label, "pill": grn_pill})

    # ---------- 2) Bills -> sirf is PO ki lines, aur unke returns ----------
    bill_blocks = []
    return_blocks = []         # saare returns ek seedhi list me (print me aakhri block ko sign lines ke saath rakhne ke liye)
    posted_bills = 0
    draft_bills = 0
    cancelled_bills = 0
    posted_returns = 0
    cancelled_returns = 0
    for invoice in sorted(invoices, key=lambda i: i.id):
        my_lines = []
        mine_total = 0
        mixed = False
        for invoice_line in invoice.lines:
            if _po_id_of(invoice_line) == po.id:
                my_lines.append(invoice_line)
                mine_total += _line_value(invoice_line)
            else:
                mixed = True               # is bill me doosre PO ke (ya remove hui GRN ke) lots bhi hain
        charges = _signed_charges(invoice.charge_lines)

        for purchase_return in sorted(invoice.returns, key=lambda r: r.id):
            if purchase_return.is_deleted:
                continue
            my_return_lines = []
            return_mine_total = 0
            return_mixed = False
            for return_line in purchase_return.lines:
                if _po_id_of(return_line.invoice_line) == po.id:
                    my_return_lines.append(return_line)
                    return_mine_total += _line_value(return_line)
                else:
                    return_mixed = True
            if not my_return_lines:
                continue                   # ye return doosre PO ke maal ka hai
            if purchase_return.status == "Cancelled":
                cancelled_returns += 1
            else:
                posted_returns += 1
            return_charges = _signed_charges(purchase_return.charge_lines)
            return_blocks.append({
                "ret": purchase_return,
                "invoice": invoice,
                "lines": my_return_lines,
                "mixed": return_mixed,
                "mine_total": round(return_mine_total, 2),
                "charges": return_charges,
                # Poore return me se jo is PO ki lines nahi: stored total - is PO ki lines - charges
                "other": round((purchase_return.total_amount or 0) - return_mine_total - return_charges, 2),
            })

        if invoice.status == "Posted":
            posted_bills += 1
        elif invoice.status == "Draft":
            draft_bills += 1
        elif invoice.status == "Cancelled":
            cancelled_bills += 1
        bill_blocks.append({
            "invoice": invoice,
            "lines": my_lines,
            "mixed": mixed,
            "mine_total": round(mine_total, 2),
            "charges": charges,
            # Poore bill me se jo is PO ki lines nahi: stored total - is PO ki lines - charges
            "other": round((invoice.total_amount or 0) - mine_total - charges, 2),
        })

    # ---------- 3) Quantity table: har PO line ka ordered / received / QC / billed / returned ----------
    quantity_rows = []
    for po_line in po.lines:
        acc = totals_by_po_line.get(po_line.id, {
            "received": 0, "passed": 0, "rejected": 0, "billed": 0, "billed_draft": 0,
            "billable": 0, "returned": 0, "lots": 0, "qc_lots": 0,
        })
        ordered = po_line.ordered_qty or 0
        received = acc["received"]
        # Jo na pass hua na reject hua: QC ke intezaar wale lots + QC ne jo adhoora chhoda, dono
        not_decided = round(max(received - acc["passed"] - acc["rejected"], 0), 4)
        quantity_rows.append({
            "line": po_line,
            "unit": _unit_code(po_line),
            "ordered": ordered,
            "received": round(received, 4),
            "left_to_receive": round(max(ordered - received, 0), 4),
            "over_received": round(max(received - ordered, 0), 4),
            "nothing_received": received <= 0,
            "qc_started": acc["qc_lots"] > 0,
            "not_decided": not_decided,
            "passed": round(acc["passed"], 4),
            "rejected": round(acc["rejected"], 4),
            "billed": round(acc["billed"], 4),
            "billed_draft": round(acc["billed_draft"], 4),
            "left_to_bill": round(acc["billable"], 4),
            "returned": round(acc["returned"], 4),
        })

    return {
        "po": _po_summary(po),
        "state": _po_state(po, quantity_rows),
        "grns": grn_blocks,
        "bills": bill_blocks,
        "returns": return_blocks,
        "quantities": quantity_rows,
        "counts": {
            "grns": len(grn_blocks),
            "draft_grns": draft_grn_count,
            "lots": lot_count,
            "draft_lots": draft_lot_count,
            "qc_done": qc_done_count,
            "qc_pending": qc_pending_count,
            "memos": memo_count,
            "bills": len(bill_blocks),
            "posted_bills": posted_bills,
            "draft_bills": draft_bills,
            "cancelled_bills": cancelled_bills,
            "returns": posted_returns + cancelled_returns,
            "cancelled_returns": cancelled_returns,
        },
    }
