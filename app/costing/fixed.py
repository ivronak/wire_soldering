# Fixed costing ka hisaab (client meeting 2, #1). Routes yahin se hisaab lete hain; production_output/routes.py output post hote hi apply_fixed_cost() chalata hai.
#
# Formula (client): din ka fixed kharcha = mahine ka kharcha / working days;  fixed per KG = din ka kharcha / us din ka total good KG.
# - Mahina shuru: Estimated amount (FixedCostPeriod, effective_from tareekh se). Output record hote waqt wahi rate batch par FREEZE (Approx).
# - Mahine ke end me Final amount: final per KG = final amount / mahine ka total good KG; us mahine ke batch ek baar Approx -> Final.
# - Purane batch ki cost kisi aur wajah se kabhi nahi badalti (naya period sirf aage ki tareekhon par lagta hai).
from datetime import date

from app.extensions import db
from app.models import FixedCostMonth, FixedCostPeriod, ProductionOrder, ProductionOutput


def output_kg(output):
    # Output ka good maal KG me (order unit KG ho to qty hi KG; PCS jaisi unit ho to qty x 1 piece ka weight)
    weight = output.production_order.unit_weight if output.production_order and output.production_order.unit_weight else 1
    return (output.good_qty or 0) * weight


def is_inhouse(output):
    # C16: in-house maal (jaise Flux: output RM store me jaata hai) bikne wala finished product nahi — fixed cost ka hissa nahi leta, KG ginti me nahi aata
    product = output.production_order.product if output.production_order else None
    return bool(product is not None and product.output_rm_id)


def costed_kg(output):
    # Fixed cost jis KG par bantta hai: sirf bikne wala finished product; in-house maal ka 0
    return 0 if is_inhouse(output) else output_kg(output)


def month_start(day):
    return day.replace(day=1)


def period_for(day):
    # Is tareekh par lagu fixed cost: effective_from <= day wali sabse nayi row (same tareekh ho to baad me jodi hui)
    return (FixedCostPeriod.query.filter(FixedCostPeriod.effective_from <= day)
            .order_by(FixedCostPeriod.effective_from.desc(), FixedCostPeriod.id.desc()).first())


def posted_outputs(start, end):
    # [start, end) ke beech ke Posted outputs (cancel hue nahi)
    return (ProductionOutput.query.filter(ProductionOutput.is_deleted == False, ProductionOutput.status == "Posted",
                                          ProductionOutput.output_date >= start, ProductionOutput.output_date < end).all())


def next_month(start):
    return date(start.year + (start.month == 12), start.month % 12 + 1, 1)


def apply_fixed_cost(output):
    """Naye output par fixed cost lagao. Fixed cost set nahi (ya KG zero) ho to kuch nahi (basis khaali = 'Material only')."""
    kg = costed_kg(output)
    output.fixed_cost_per_kg, output.fixed_cost_total, output.fixed_cost_basis = 0, 0, None
    if kg <= 0:
        return
    day = output.output_date
    start = month_start(day)
    final = FixedCostMonth.query.filter_by(month_start=start).first()
    if final:
        per_kg, basis = final.final_per_kg, "Final"        # mahina finalize ho chuka: late entry bhi final rate par
    else:
        period = period_for(day)
        if not period or not period.working_days:
            return
        # Us din ka total good KG (is output samet): din ka kharcha usi par baantta hai
        day_kg = kg + sum(costed_kg(o) for o in posted_outputs(day, date.fromordinal(day.toordinal() + 1)) if o.id != output.id)
        per_kg, basis = (period.monthly_amount / period.working_days) / day_kg, "Approx"
    output.fixed_cost_per_kg = round(per_kg, 4)
    output.fixed_cost_total = round(per_kg * kg, 2)
    output.fixed_cost_basis = basis


def finalize_month(start, final_amount):
    """Mahina finalize: (True, FixedCostMonth) ya (False, error text). Us mahine ke saare Posted outputs Final rate par ek baar restate."""
    if FixedCostMonth.query.filter_by(month_start=start).first():
        return False, "This month is already finalised. A finalised month cannot be changed."
    if start > month_start(date.today()):
        return False, "A month that has not started yet cannot be finalised."
    if final_amount <= 0:
        return False, "Final fixed cost must be greater than zero."
    outputs = posted_outputs(start, next_month(start))
    total_kg = sum(costed_kg(o) for o in outputs)
    if total_kg <= 0:
        return False, "No good output was recorded in this month, so a final cost per KG cannot be worked out."
    per_kg = final_amount / total_kg
    row = FixedCostMonth(month_start=start, final_amount=round(final_amount, 2), total_kg=round(total_kg, 4), final_per_kg=round(per_kg, 4))
    db.session.add(row)
    for o in outputs:
        kg = costed_kg(o)
        if kg <= 0:
            continue                # in-house maal par fixed cost nahi lagta
        o.fixed_cost_per_kg = row.final_per_kg
        o.fixed_cost_total = round(row.final_per_kg * kg, 2)
        o.fixed_cost_basis = "Final"
    return True, row


def product_cost_per_unit(output):
    # (material + fixed) / good qty — order ki unit me. Material = WIP se use hue RM ki value (output.total_value).
    if not output.good_qty:
        return 0.0
    return ((output.total_value or 0) + (output.fixed_cost_total or 0)) / output.good_qty
