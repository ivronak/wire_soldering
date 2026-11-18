# Sales S4 — Invoice ka hisaab: challan se bill banana, loss gate (rate cost se kam), customer ledger me post / reverse.
# Judta hai: delivery_challans (kya bheja, cost kya thi), quotations (rate / discount / GST / charges), customers.ledger (lena baaki).
#
# Rules (memory.md S4 decision):
#   * Invoice challan(on) ke dispatched maal par banta hai — order ki qty par nahi (extra bheja to extra ka bhi bill).
#   * Rate / discount / GST quotation line se aate hain; invoice par rate / discount badal sakte hain.
#   * Charges (Shipping...) sirf us quotation ke PEHLE invoice par aate hain, baad ke invoices par nahi.
#   * Loss gate: kisi line ka (discount ke baad) rate us line ki asli cost se zara bhi kam ho to invoice "Waiting approval" me rukta hai.
#     Owner approve kare tab hi Posted hota hai (customer ledger me Dr). Abhi login / roles nahi hain, isliye approve ka button sabko dikhta hai.
#   * Ledger sign rule (project): Cr = plus, Dr = minus. Customer se paisa LENA hai => Dr => current_balance ghatta hai.
from datetime import datetime

from app.costing.full_cost import batch_full_cost
from app.extensions import db
from app.models import DeliveryChallan, SalesInvoice, SalesInvoiceCharge, SalesInvoiceLine


class BillingError(Exception):
    pass


def unbilled_challans(quotation):
    # Is quotation ke challan jinka bill abhi nahi bana (Cancelled challan nahi)
    return [c for c in quotation.challans if c.status == "Dispatched" and not c.is_deleted and c.invoice_id is None]


def active_invoices(quotation):
    return [i for i in quotation.invoices if i.status != "Cancelled" and not i.is_deleted]


def challan_totals(challans):
    """{quotation_line: {"qty": jod, "cost": weighted per-unit cost}} — challan lines ko quotation line ke hisaab se jodta hai.
    Cost = batch ki POORI cost abhi ki (material + fixed overhead; mahina finalize hua ho to Final rate) — sirf material nahi, warna loss chhoot jaata hai."""
    out = {}
    for challan in challans:
        for cl in challan.lines:
            row = out.setdefault(cl.quotation_line, {"qty": 0.0, "value": 0.0})
            row["qty"] += cl.qty
            row["value"] += cl.qty * batch_full_cost(cl.batch)
    for row in out.values():
        row["cost"] = round(row["value"] / row["qty"], 4) if row["qty"] else 0
    return out


def next_invoice_no(invoice_date):
    # INV-<saal>-<agla number>: sabse bada number dekhte hain (count nahi), taaki gap hone par bhi number repeat na ho
    prefix = f"INV-{invoice_date.year}-"
    last = 0
    for (number,) in db.session.query(SalesInvoice.invoice_no).filter(SalesInvoice.invoice_no.like(prefix + "%")).all():
        try:
            last = max(last, int(number.split("-")[-1]))
        except ValueError:
            pass
    return f"{prefix}{last + 1:03d}"


def _post(invoice):
    # Customer ledger me Dr: lena baaki badha => current_balance minus ki taraf
    ledger = invoice.quotation.customer.ledger
    ledger.current_balance = round(ledger.current_balance - invoice.total_amount, 2)
    invoice.status = "Posted"


def create_invoice(quotation, challans, invoice_date, rates, discounts, remarks=None):
    """challans = chune hue (bill nahi bane) challan. rates / discounts = {quotation_line_id: float} (na ho to quotation wali).
    Invoice + lines + charges banata hai, totals aur loss nikalta hai. Loss ho to 'Waiting approval', warna seedha Posted. Galti par BillingError."""
    if not challans:
        raise BillingError("Choose at least one challan to bill.")
    for challan in challans:
        if challan.quotation_id != quotation.id or challan.status != "Dispatched" or challan.is_deleted:
            raise BillingError(f"Challan {challan.challan_no} cannot be billed here.")
        if challan.invoice_id is not None:
            raise BillingError(f"Challan {challan.challan_no} is already billed.")
    totals = challan_totals(challans)
    if not totals:
        raise BillingError("The chosen challans have no goods.")

    invoice = SalesInvoice(invoice_no=next_invoice_no(invoice_date), quotation_id=quotation.id, invoice_date=invoice_date,
                           tax_type="inter" if quotation.is_inter_state else "intra", status="Posted", remarks=remarks)
    db.session.add(invoice)
    db.session.flush()

    for qline in quotation.lines:                      # quotation ki line ka order hi invoice me rakhte hain
        if qline not in totals:
            continue
        rate = rates.get(qline.id, qline.rate)
        discount = discounts.get(qline.id, qline.discount_percent or 0)
        if rate < 0:
            raise BillingError(f"{qline.product.name}: rate cannot be negative.")
        if discount < 0 or discount > 100:
            raise BillingError(f"{qline.product.name}: discount must be between 0 and 100.")
        db.session.add(SalesInvoiceLine(invoice_id=invoice.id, quotation_line_id=qline.id, qty=round(totals[qline]["qty"], 4), rate=rate,
                                        discount_percent=discount, tax_rate_id=qline.tax_rate_id, unit_cost=totals[qline]["cost"]))

    # Charges: quotation ke charges sirf pehle (abhi tak koi active invoice nahi) invoice par
    if not active_invoices_before(quotation, invoice):
        for row in quotation.charge_lines:
            db.session.add(SalesInvoiceCharge(invoice_id=invoice.id, charge_id=row.charge_id, amount=row.amount, effect=row.effect))
    db.session.flush()
    db.session.refresh(invoice)

    result = invoice.summary
    if result["grand_total"] < 0:
        raise BillingError("The invoice total cannot be negative.")
    invoice.subtotal = round(result["items_total"] - result["discount_total"], 2)
    invoice.charges_total = result["charges_net"]
    invoice.tax_total = result["tax_total"]
    invoice.total_amount = result["grand_total"]
    invoice.cost_total = round(sum(line.unit_cost * line.qty for line in invoice.lines), 2)
    invoice.loss_amount = round(sum(line.loss_value for line in invoice.lines), 2)
    invoice.has_loss = invoice.loss_amount > 0

    for challan in challans:
        challan.invoice_id = invoice.id
    if invoice.has_loss:
        invoice.status = "Waiting approval"            # Owner approve kare tab hi ledger me jaayega
    else:
        _post(invoice)
    db.session.flush()
    return invoice


def active_invoices_before(quotation, new_invoice):
    # Naye invoice ke alawa is quotation ke active (Cancelled nahi) invoices
    return [i for i in quotation.invoices if i.id != new_invoice.id and i.status != "Cancelled" and not i.is_deleted]


def approve_loss(invoice, note):
    """Owner ne loss par bill chhapne ki ijaazat di: Waiting approval -> Posted (ledger me Dr)."""
    if invoice.status != "Waiting approval":
        raise BillingError("This invoice is not waiting for approval.")
    invoice.loss_note = note
    invoice.loss_approved_at = datetime.utcnow()
    _post(invoice)
    db.session.flush()


def cancel_invoice(invoice, reason):
    """Invoice cancel: Posted tha to ledger ka asar wapas; challan phir 'bill nahi bana' ho jaate hain (dobara bill ban sakta hai)."""
    if invoice.status == "Cancelled":
        raise BillingError("This invoice is already cancelled.")
    if invoice.status == "Posted":
        ledger = invoice.quotation.customer.ledger
        ledger.current_balance = round(ledger.current_balance + invoice.total_amount, 2)
    for challan in list(invoice.challans):
        challan.invoice_id = None
    invoice.status = "Cancelled"
    invoice.cancel_reason = reason
    invoice.cancelled_at = datetime.utcnow()
    db.session.flush()


def billing_state(quotation):
    # Ordered quotation ka bill haal: dispatched maal me se kitna bill hua. "Not billed" / "Partly billed" / "Billed" / None (kuch dispatch hi nahi hua)
    sent = 0.0
    for challan in quotation.challans:
        if challan.status == "Dispatched" and not challan.is_deleted:
            sent += sum(cl.qty for cl in challan.lines)
    if sent <= 0.00005:
        return None
    billed = 0.0
    for invoice in active_invoices(quotation):
        billed += sum(line.qty for line in invoice.lines)
    if billed <= 0.00005:
        return "Not billed"
    if billed + 0.00005 >= sent:
        return "Billed"
    return "Partly billed"
