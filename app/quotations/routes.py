# Sales S1 — Quotation: customer ko bhejne wali quotation banana, list, detail aur status (Sent / Approved / Rejected / Cancelled).
# Customer Master, Product Master, Tax Rates aur Payment Terms se juda hai. Agla step: Finalize -> Production order (is file me abhi nahi).
from datetime import date, datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import Charge, Customer, PaymentTerm, Product, Quotation, QuotationCharge, QuotationLine, QuotationRevision, TaxRate
from app.tax import line_value

quotations_bp = Blueprint("quotations", __name__, template_folder="templates")

# Kaun sa status kahan jaa sakta hai. Approved ke baad Finalize alag step hai, Rejected / Cancelled par kuch nahi.
NEXT_STATUS = {
    "Draft": ("Sent", "Cancelled"),
    "Sent": ("Approved", "Rejected"),
}
TABS = {
    "open": ("Draft", "Sent"),
    "approved": ("Approved",),
    "closed": ("Rejected", "Cancelled"),
}


def sellable_products():
    # Quotation me wahi product jo bik sakta hai: active aur in-house semi-finished (jaise Flux, output_rm_id) nahi
    return Product.query.filter(Product.is_deleted == False, Product.is_active == True, Product.output_rm_id.is_(None)).order_by(Product.code).all()


def next_quote_no(quote_date):
    # QT-<saal>-<agla number>. Count nahi, sabse bada number dekhte hain taaki beech ka koi hat jaye to bhi number repeat na ho
    prefix = f"QT-{quote_date.year}-"
    last = 0
    for (number,) in db.session.query(Quotation.quote_no).filter(Quotation.quote_no.like(prefix + "%")).all():
        try:
            last = max(last, int(number.split("-")[-1]))
        except ValueError:
            pass
    return f"{prefix}{last + 1:03d}"


def is_expired(quotation):
    # Bheji hui (ya Draft) quotation ki validity nikal gayi ho to list me "Expired" chip; status badalta nahi, sirf dikhta hai
    return quotation.status in ("Draft", "Sent") and quotation.valid_until is not None and quotation.valid_until < date.today()


def form_context():
    # "New quotation" drawer ka saara data: customers (state + payment terms), products (last rate + GST), charges, GST rates, hamari branch ka state
    from app.models import Branch
    customers = Customer.query.filter(Customer.is_deleted == False, Customer.is_active == True).order_by(Customer.name).all()
    branch = Branch.query.filter_by(is_deleted=False, is_active=True).order_by(Branch.id).first()
    # Product ka pichhla quote kiya rate (hint). Naye se purana: pehla mila wahi last rate
    last_rate = {}
    for line in QuotationLine.query.join(Quotation).filter(Quotation.is_deleted == False).order_by(QuotationLine.id.desc()).all():
        last_rate.setdefault(line.product_id, line.rate)
    products = [{"id": p.id, "code": p.code, "name": p.name, "unit": p.base_unit.code if p.base_unit else "",
                 "tax_rate_id": p.tax_rate_id, "tax_label": p.tax_rate.label if p.tax_rate else "", "tax_pct": p.tax_rate.rate_percent if p.tax_rate else 0,
                 "last_rate": last_rate.get(p.id)} for p in sellable_products()]
    return {
        "customers": customers, "products": products,
        "customer_rows": [{"id": c.id, "state_id": c.state_id, "payment_terms_id": c.payment_terms_id} for c in customers],
        "company_state_id": branch.state_id if branch else None, "today": date.today().isoformat(),
        "charges": Charge.query.filter_by(is_deleted=False, is_active=True).order_by(Charge.name).all(),
        "payment_terms": PaymentTerm.query.filter_by(is_deleted=False, is_active=True).order_by(PaymentTerm.name).all(),
    }


@quotations_bp.route("/quotations")
def quotations_list():
    tab = (request.args.get("tab") or "open").strip().lower()
    if tab not in TABS:
        tab = "open"
    base = Quotation.query.filter(Quotation.is_deleted == False)
    counts = {key: base.filter(Quotation.status.in_(statuses)).count() for key, statuses in TABS.items()}
    quotations = base.filter(Quotation.status.in_(TABS[tab])).order_by(Quotation.id.desc()).all()
    return render_template("quotations.html", active_nav="quotations", tab=tab, counts=counts, quotations=quotations, is_expired=is_expired,
                           open_new=request.args.get("new") == "1", **form_context())


@quotations_bp.route("/quotations/new")
def quotations_new():
    # Purana link: ab "New quotation" list page par drawer me khulta hai
    return redirect(url_for("quotations.quotations_list", new=1))

def _read_date(name, required=False):
    raw = (request.form.get(name) or "").strip()
    if not raw:
        return None, ("Enter a date." if required else None)
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date(), None
    except ValueError:
        return None, "Enter a valid date."


def read_form(customer=None):
    """Drawer ka form padhke check karta hai (naya quotation ya edit / revise dono ke liye).
    Return (data, error). customer=None -> form se customer chuna jaata hai (naya); edit me customer wahi rehta hai, badalta nahi."""
    if customer is None:
        customer = db.session.get(Customer, request.form.get("customer_id", type=int) or 0)
        if customer is None or customer.is_deleted or not customer.is_active:
            return None, "Choose an active customer."
    quote_date, error = _read_date("quote_date", required=True)
    if error:
        return None, "Quotation date: " + error
    valid_until, error = _read_date("valid_until")
    if error:
        return None, "Valid until: " + error
    needed_by, error = _read_date("needed_by_date")
    if error:
        return None, "Needed by: " + error
    if valid_until and valid_until < quote_date:
        return None, "Valid until cannot be before the quotation date."
    terms_id = request.form.get("payment_terms_id", type=int)
    if terms_id and not PaymentTerm.query.filter_by(id=terms_id, is_deleted=False).first():
        return None, "Choose valid payment terms."

    # Lines: product_id_0, qty_0, rate_0, discount_0 ... (kitni lines aayi wo "line_count" se)
    lines = []
    seen = set()
    for index in range(request.form.get("line_count", type=int) or 0):
        product_id = request.form.get(f"product_id_{index}", type=int)
        if not product_id:
            continue                                                           # khaali chhodi hui row ignore
        product = db.session.get(Product, product_id)
        if product is None or product.is_deleted or not product.is_active or product.output_rm_id:
            return None, "Line %d: choose a product that can be sold." % (len(lines) + 1)
        if product_id in seen:
            return None, f"{product.name} is on two lines. Keep one line per product."
        seen.add(product_id)
        qty = request.form.get(f"qty_{index}", type=float)
        rate = request.form.get(f"rate_{index}", type=float)
        discount = request.form.get(f"discount_{index}", type=float) or 0.0
        # GST hamesha Product master ka (Tax Master se chuna hua) — form se nahi badalta. Line par id copy hota hai, taaki baad me product ka tax badle to purani quotation na badle.
        tax_rate_id = product.tax_rate_id
        if qty is None or qty <= 0:
            return None, f"{product.name}: quantity must be more than zero."
        if rate is None or rate <= 0:
            return None, f"{product.name}: enter the rate (more than zero)."
        if discount < 0 or discount > 100:
            return None, f"{product.name}: discount must be between 0 and 100 %."
        if not db.session.get(TaxRate, tax_rate_id):
            return None, f"{product.name}: its GST rate is missing in the Product master. Set it there first."
        lines.append({"product_id": product_id, "qty": qty, "rate": rate, "discount_percent": discount, "tax_rate_id": tax_rate_id,
                      "remarks": (request.form.get(f"remarks_{index}") or "").strip()[:150] or None})
    if not lines:
        return None, "Add at least one product line."

    # Charges (Shipping, Labour ...): charge_id_N, charge_amount_N, charge_effect_N — Charges Master se, Add ya Minus (PO jaisa)
    charges = []
    for index in range(request.form.get("charge_count", type=int) or 0):
        charge_id = request.form.get(f"charge_id_{index}", type=int)
        amount_raw = (request.form.get(f"charge_amount_{index}") or "").strip()
        if not charge_id and not amount_raw:
            continue                                                           # khaali row ignore
        effect = (request.form.get(f"charge_effect_{index}") or "").strip()
        charge = db.session.get(Charge, charge_id) if charge_id else None
        if charge is None or charge.is_deleted or not charge.is_active:
            return None, "Choose a charge from the list."
        try:
            amount = float(amount_raw)
        except ValueError:
            amount = 0
        if amount <= 0:
            return None, f"{charge.name}: enter an amount more than zero."
        if effect not in ("add", "minus"):
            return None, f"{charge.name}: choose Add or Minus."
        charges.append({"charge_id": charge.id, "amount": round(amount, 2), "effect": effect})
    # Minus charges items ke total se zyada nahi ho sakte (total zero se neeche nahi jaana chahiye)
    items_after_discount = sum(round(line_value(l["qty"], l["rate"]) * (1 - l["discount_percent"] / 100), 2) for l in lines)
    charges_net = sum(-c["amount"] if c["effect"] == "minus" else c["amount"] for c in charges)
    if items_after_discount + charges_net < 0:
        return None, "The charges take the total below zero. Check the Minus amounts."

    return {
        "customer": customer, "quote_date": quote_date, "valid_until": valid_until, "needed_by": needed_by,
        "payment_terms_id": terms_id or customer.payment_terms_id,
        "delivery_terms": (request.form.get("delivery_terms") or "").strip()[:255] or None,
        "terms": (request.form.get("terms") or "").strip()[:500] or None,
        "notes": (request.form.get("notes") or "").strip()[:255] or None,
        "lines": lines, "charges": charges,
    }, None


def _fill(quotation, data):
    # Header + lines + charges ko data se bharta hai (naye quotation me bhi, edit / revise me bhi)
    quotation.quote_date = data["quote_date"]
    quotation.valid_until = data["valid_until"]
    quotation.needed_by_date = data["needed_by"]
    quotation.payment_terms_id = data["payment_terms_id"]
    quotation.delivery_terms = data["delivery_terms"]
    quotation.terms = data["terms"]
    quotation.notes = data["notes"]
    quotation.lines = [QuotationLine(**spec) for spec in data["lines"]]
    quotation.charge_lines = [QuotationCharge(**spec) for spec in data["charges"]]


def snapshot(quotation):
    """Quotation ka abhi ka roop (JSON) — revision me purana roop isi se rakhte hain. Product / tax ke naam bhi copy, taaki master badle to bhi history waisi hi dikhe."""
    summary = quotation.summary
    return {
        "quote_date": quotation.quote_date.isoformat(),
        "valid_until": quotation.valid_until.isoformat() if quotation.valid_until else None,
        "needed_by_date": quotation.needed_by_date.isoformat() if quotation.needed_by_date else None,
        "payment_terms": quotation.payment_terms.name if quotation.payment_terms else None,
        "delivery_terms": quotation.delivery_terms, "terms": quotation.terms,
        "lines": [{"product": line.product.name, "code": line.product.code, "qty": line.qty, "rate": line.rate, "discount": line.discount_percent,
                   "tax": (f"{line.tax_rate.label} {line.tax_rate.rate_percent:g}%" if line.tax_rate else None), "amount": line.net_value}
                  for line in quotation.lines],
        "charges": [{"name": row["name"], "amount": row["amount"], "effect": row["effect"]} for row in summary["charge_rows"]],
        "taxable": summary["taxable_total"], "grand_total": summary["grand_total"],
    }


def _short(value):
    if not value:
        return "—"
    return value if len(value) <= 60 else value[:57] + "..."


def diff_versions(old, new):
    """Do snapshot ka farak, seedhe shabdon me (list of text). Revision history me yahi dikhta hai."""
    out = []
    old_lines = {l["code"]: l for l in old["lines"]}
    new_lines = {l["code"]: l for l in new["lines"]}
    for code, line in new_lines.items():
        before = old_lines.get(code)
        if before is None:
            out.append(f"{line['product']}: added ({line['qty']:g} at ₹{line['rate']:g})")
            continue
        parts = []
        if before["rate"] != line["rate"]:
            parts.append(f"rate ₹{before['rate']:g} → ₹{line['rate']:g}")
        if before["qty"] != line["qty"]:
            parts.append(f"quantity {before['qty']:g} → {line['qty']:g}")
        if before["discount"] != line["discount"]:
            parts.append(f"discount {before['discount']:g}% → {line['discount']:g}%")
        if before["tax"] != line["tax"]:
            parts.append(f"GST {before['tax']} → {line['tax']}")
        if parts:
            out.append(f"{line['product']}: " + ", ".join(parts))
    for code, line in old_lines.items():
        if code not in new_lines:
            out.append(f"{line['product']}: removed")
    old_ch = {(c["name"], c["effect"]): c["amount"] for c in old["charges"]}
    new_ch = {(c["name"], c["effect"]): c["amount"] for c in new["charges"]}
    for key, amount in new_ch.items():
        sign = "−" if key[1] == "minus" else "+"
        if key not in old_ch:
            out.append(f"{key[0]}: added ({sign} ₹{amount:g})")
        elif old_ch[key] != amount:
            out.append(f"{key[0]}: ₹{old_ch[key]:g} → ₹{amount:g}")
    for key in old_ch:
        if key not in new_ch:
            out.append(f"{key[0]}: removed")
    for field, label in (("valid_until", "Valid until"), ("needed_by_date", "Needed by"), ("payment_terms", "Payment terms"),
                         ("delivery_terms", "Delivery terms"), ("terms", "Other terms")):
        if (old[field] or None) != (new[field] or None):
            out.append(f"{label}: {_short(old[field])} → {_short(new[field])}")
    return out


@quotations_bp.route("/quotations/add", methods=["POST"])
def quotations_add():
    data, error = read_form()
    if error:
        flash(error, "error")
        return redirect(url_for("quotations.quotations_list", new=1))
    quotation = Quotation(quote_no=next_quote_no(data["quote_date"]), customer_id=data["customer"].id, status="Draft", revision_no=0)
    _fill(quotation, data)
    db.session.add(quotation)
    db.session.commit()
    flash(f"Quotation {quotation.quote_no} saved as Draft. Mark it Sent once you give it to the customer.", "success")
    return redirect(url_for("quotations.quotations_detail", quotation_id=quotation.id))


@quotations_bp.route("/quotations/<int:quotation_id>/update", methods=["POST"])
def quotations_update(quotation_id):
    """Draft = seedha edit (koi revision nahi, customer ko abhi gayi nahi). Sent = Revise: R1 / R2 ban-ta hai, purana roop history me, wajah zaroori,
    aur quotation wapas Draft (customer ko dobara Sent karna padega). Approved / Rejected / Cancelled badalti nahi."""
    quotation = Quotation.query.filter_by(id=quotation_id, is_deleted=False).first_or_404()
    back = redirect(url_for("quotations.quotations_detail", quotation_id=quotation.id, edit=1))
    done = redirect(url_for("quotations.quotations_detail", quotation_id=quotation.id))
    if quotation.status not in ("Draft", "Sent"):
        flash(f"A {quotation.status} quotation cannot be changed.", "error")
        return done
    data, error = read_form(customer=quotation.customer)
    if error:
        flash(error, "error")
        return back
    revising = quotation.status == "Sent"
    reason = (request.form.get("revision_note") or "").strip()[:255]
    if revising and len(reason) < 3:
        flash("Write why the quotation is being revised (for example: customer asked for a lower rate).", "error")
        return back
    before = snapshot(quotation)
    # Purani lines / charges hatao (purana roop revision snapshot me safe hai), phir naye bharo
    for row in list(quotation.lines) + list(quotation.charge_lines):
        db.session.delete(row)
    db.session.flush()
    db.session.expire(quotation, ["lines", "charge_lines"])
    _fill(quotation, data)
    db.session.flush()
    db.session.expire(quotation, ["lines", "charge_lines"])
    after = snapshot(quotation)
    if revising:
        quotation.revision_no += 1
        quotation.status = "Draft"
        db.session.add(QuotationRevision(quotation_id=quotation.id, revision_no=quotation.revision_no, note=reason, snapshot=before,
                                         changes="\n".join(diff_versions(before, after)) or None,
                                         old_total=before["grand_total"], new_total=after["grand_total"]))
        flash(f"{quotation.quote_no} revised to R{quotation.revision_no}. Mark it Sent again when you give the new rates to the customer.", "success")
    else:
        flash(f"{quotation.quote_no} updated.", "success")
    db.session.commit()
    return done


def edit_data(quotation):
    # Detail page ka Edit / Revise drawer isi se pehle se bhara aata hai (JSON)
    return {
        "action": url_for("quotations.quotations_update", quotation_id=quotation.id),
        "customer_id": quotation.customer_id, "quote_date": quotation.quote_date.isoformat(),
        "valid_until": quotation.valid_until.isoformat() if quotation.valid_until else "",
        "needed_by_date": quotation.needed_by_date.isoformat() if quotation.needed_by_date else "",
        "payment_terms_id": quotation.payment_terms_id or "", "delivery_terms": quotation.delivery_terms or "",
        "terms": quotation.terms or "", "notes": quotation.notes or "",
        "lines": [{"product_id": l.product_id, "qty": l.qty, "rate": l.rate, "discount": l.discount_percent} for l in quotation.lines],
        "charges": [{"charge_id": c.charge_id, "amount": c.amount, "effect": c.effect} for c in quotation.charge_lines],
        "revising": quotation.status == "Sent", "label": f"{quotation.quote_no} · R{quotation.revision_no}",
        "next_revision": quotation.revision_no + 1,
    }


@quotations_bp.route("/quotations/<int:quotation_id>")
def quotations_detail(quotation_id):
    quotation = Quotation.query.filter_by(id=quotation_id, is_deleted=False).first_or_404()
    editable = quotation.status in ("Draft", "Sent")
    return render_template("quotation_detail.html", active_nav="quotations", q=quotation, summary=quotation.summary,
                           next_statuses=NEXT_STATUS.get(quotation.status, ()), expired=is_expired(quotation),
                           edit=edit_data(quotation) if editable else None, open_edit=request.args.get("edit") == "1" and editable,
                           revisions=list(reversed(quotation.revisions)), **(form_context() if editable else {}))


@quotations_bp.route("/quotations/<int:quotation_id>/print")
def quotations_print(quotation_id):
    # Customer ko dene wala A4 print (letterhead). Internal note print me nahi aata.
    quotation = Quotation.query.filter_by(id=quotation_id, is_deleted=False).first_or_404()
    return render_template("quotation_print.html", q=quotation, summary=quotation.summary)


@quotations_bp.route("/quotations/<int:quotation_id>/status", methods=["POST"])
def quotations_status(quotation_id):
    quotation = Quotation.query.filter_by(id=quotation_id, is_deleted=False).first_or_404()
    target = (request.form.get("to") or "").strip()
    back = redirect(url_for("quotations.quotations_detail", quotation_id=quotation.id))
    if target not in NEXT_STATUS.get(quotation.status, ()):
        flash(f"A {quotation.status} quotation cannot be marked {target or 'that'}.", "error")
        return back
    quotation.status = target
    db.session.commit()
    messages = {"Sent": "marked Sent to the customer.", "Approved": "approved by the customer.",
                "Rejected": "marked Rejected.", "Cancelled": "cancelled."}
    flash(f"{quotation.quote_no} {messages[target]}", "success")
    return back
