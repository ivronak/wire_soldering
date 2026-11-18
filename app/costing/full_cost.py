# Poori cost (material + fixed overhead) per unit — Sales ka loss gate aur quotation ki "price below cost" warning yahin se cost lete hain.
#
# Kyun alag file: FGBatch.unit_cost sirf MATERIAL cost hai (output.total_value / good qty). Mahine ka fixed kharcha (salary, bijli ...)
# output par alag (fixed_cost_total) rehta hai (app/costing/fixed.py). Asli "kharcha per piece" dono ka jod hai — isliye bikri ka bhaav
# material se kam par nahi, poori cost se milana chahiye.
from app.costing.fixed import product_cost_per_unit
from app.extensions import db
from app.models import ProductionOrder, ProductionOutput


def batch_full_cost(batch):
    # Batch ki poori cost per unit. Output mil jaye to (material + fixed) / good qty, warna batch ki apni (material) cost
    output = batch.output
    if output is not None and output.good_qty:
        return round(product_cost_per_unit(output), 4)
    return round(batch.unit_cost or 0, 4)


def last_made_cost(product_id):
    """Is product ka sabse nayi Posted output ki poori cost per unit — {"cost", "batch_no", "date", "fixed"} ya None (kabhi bana hi nahi).
    Quotation ke waqt yahi 'andaaza' hai: asli cost production ke baad hi pakki hoti hai, isliye isko warning ki tarah dikhate hain, rok nahi."""
    output = (ProductionOutput.query.join(ProductionOrder, ProductionOrder.id == ProductionOutput.production_order_id)
              .filter(ProductionOrder.product_id == product_id, ProductionOutput.status == "Posted", ProductionOutput.is_deleted == False,
                      ProductionOutput.good_qty > 0)
              .order_by(ProductionOutput.id.desc()).first())
    if output is None:
        return None
    return {"cost": round(product_cost_per_unit(output), 2), "batch_no": output.batch_no, "date": output.output_date.strftime("%d %b %Y"),
            "fixed": bool(output.fixed_cost_total)}


def last_costs(product_ids):
    # {product_id: last_made_cost(...)} sirf unke liye jinki cost mili
    out = {}
    for pid in set(product_ids):
        info = last_made_cost(pid)
        if info:
            out[pid] = info
    return out
