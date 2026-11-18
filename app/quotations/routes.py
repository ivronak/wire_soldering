# Sales S1 — Quotation: customer ko bhejne wali quotation banana, list, detail aur status (Sent / Approved / Rejected / Cancelled).
# Customer Master, Product Master, Tax Rates aur Payment Terms se juda hai. Agla step: Finalize -> Production order (is file me abhi nahi).
from datetime import date, datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import Charge, Customer, PaymentTerm, Product, Quotation, QuotationCharge, QuotationLine, TaxRate

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


@quotations_bp.route("/quotations/add", methods=["POST"])
def quotations_add():
    back = url_for("quotations.quotations_list", new=1)
    customer = db.session.get(Customer, request.form.get("customer_id", type=int) or 0)
    if customer is None or customer.is_deleted or not customer.is_active:
        flash("Choose an active customer.", "error")
        return redirect(back)
    quote_date, error = _read_date("quote_date", required=True)
    if error:
        flash("Quotation date: " + error, "error")
        return redirect(back)
    valid_until, error = _read_date("valid_until")
    if error:
        flash("Valid until: " + error, "error")
        return redirect(back)
    needed_by, error = _read_date("needed_by_date")
    if error:
        flash("Needed by: " + error, "error")
        return redirect(back)
    if valid_until and valid_until < quote_date:
        flash("Valid until cannot be before the quotation date.", "error")
        return redirect(back)
    terms_id = request.form.get("payment_terms_id", type=int)
    if terms_id and not PaymentTerm.query.filter_by(id=terms_id, is_deleted=False).first():
        flash("Choose valid payment terms.", "error")
        return redirect(back)

    # Lines: product_id_0, qty_0, rate_0, discount_0, tax_rate_id_0 ... (kitni lines aayi wo "line_count" se)
    lines = []
    seen = set()
    for index in range(request.form.get("line_count", type=int) or 0):
        product_id = request.form.get(f"product_id_{index}", type=int)
        if not product_id:
            continue                                                           # khaali chhodi hui row ignore
        product = db.session.get(Product, product_id)
        if product is None or product.is_deleted or not product.is_active or product.output_rm_id:
            flash("Line %d: choose a product that can be sold." % (len(lines) + 1), "error")
            return redirect(back)
        if product_id in seen:
            flash(f"{product.name} is on two lines. Keep one line per product.", "error")
            return redirect(back)
        seen.add(product_id)
        qty = request.form.get(f"qty_{index}", type=float)
        rate = request.form.get(f"rate_{index}", type=float)
        discount = request.form.get(f"discount_{index}", type=float) or 0.0
        # GST hamesha Product master ka (Tax Master se chuna hua) — form se nahi badalta. Line par rate copy hota hai, taaki baad me product ka tax badle to purani quotation na badle.
        tax_rate_id = product.tax_rate_id
        if qty is None or qty <= 0:
            flash(f"{product.name}: quantity must be more than zero.", "error")
            return redirect(back)
        if rate is None or rate <= 0:
            flash(f"{product.name}: enter the rate (more than zero).", "error")
            return redirect(back)
        if discount < 0 or discount > 100:
            flash(f"{product.name}: discount must be between 0 and 100 %.", "error")
            return redirect(back)
        if not db.session.get(TaxRate, tax_rate_id):
            flash(f"{product.name}: its GST rate is missing in the Product master. Set it there first.", "error")
            return redirect(back)
        lines.append(QuotationLine(product_id=product_id, qty=qty, rate=rate, discount_percent=discount, tax_rate_id=tax_rate_id,
                                   remarks=(request.form.get(f"remarks_{index}") or "").strip()[:150] or None))
    if not lines:
        flash("Add at least one product line.", "error")
        return redirect(back)

    # Charges (Shipping, Labour ...): charge_id_N, charge_amount_N, charge_effect_N — Charges Master se, Add ya Minus (PO jaisa)
    charge_rows = []
    for index in range(request.form.get("charge_count", type=int) or 0):
        charge_id = request.form.get(f"charge_id_{index}", type=int)
        amount_raw = (request.form.get(f"charge_amount_{index}") or "").strip()
        if not charge_id and not amount_raw:
            continue                                                           # khaali row ignore
        effect = (request.form.get(f"charge_effect_{index}") or "").strip()
        charge = db.session.get(Charge, charge_id) if charge_id else None
        if charge is None or charge.is_deleted or not charge.is_active:
            flash("Choose a charge from the list.", "error")
            return redirect(back)
        try:
            amount = float(amount_raw)
        except ValueError:
            amount = 0
        if amount <= 0:
            flash(f"{charge.name}: enter an amount more than zero.", "error")
            return redirect(back)
        if effect not in ("add", "minus"):
            flash(f"{charge.name}: choose Add or Minus.", "error")
            return redirect(back)
        charge_rows.append(QuotationCharge(charge_id=charge.id, amount=round(amount, 2), effect=effect))
    # Minus charges items ke total se zyada nahi ho sakte (total zero se neeche nahi jaana chahiye)
    items_after_discount = sum(line.net_value for line in lines)
    charges_net = sum(-row.amount if row.effect == "minus" else row.amount for row in charge_rows)
    if items_after_discount + charges_net < 0:
        flash("The charges take the total below zero. Check the Minus amounts.", "error")
        return redirect(back)

    quotation = Quotation(
        quote_no=next_quote_no(quote_date), customer_id=customer.id, quote_date=quote_date, valid_until=valid_until, needed_by_date=needed_by,
        payment_terms_id=terms_id or customer.payment_terms_id,
        delivery_terms=(request.form.get("delivery_terms") or "").strip()[:255] or None,
        terms=(request.form.get("terms") or "").strip()[:500] or None,
        notes=(request.form.get("notes") or "").strip()[:255] or None,
        status="Draft", revision_no=0,
    )
    quotation.lines = lines
    quotation.charge_lines = charge_rows
    db.session.add(quotation)
    db.session.commit()
    flash(f"Quotation {quotation.quote_no} saved as Draft. Mark it Sent once you give it to the customer.", "success")
    return redirect(url_for("quotations.quotations_detail", quotation_id=quotation.id))


@quotations_bp.route("/quotations/<int:quotation_id>")
def quotations_detail(quotation_id):
    quotation = Quotation.query.filter_by(id=quotation_id, is_deleted=False).first_or_404()
    return render_template("quotation_detail.html", active_nav="quotations", q=quotation, summary=quotation.summary,
                           next_statuses=NEXT_STATUS.get(quotation.status, ()), expired=is_expired(quotation))


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
