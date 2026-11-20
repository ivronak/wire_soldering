# Extra pieces % ka hisaab (20 Nov 2026): customer ko jitna chahiye (base qty) usse extra_percent % zyada banate hain.
#   planned_qty = base qty x (1 + extra% / 100)
# Pieces (PCS / spool / box) me upar round (adha piece nahi banta); KG me 2 decimal. Recipe / packing is planned_qty se nikalti hai.
# Scrap / wastage ka cushion yahan nahi — wo material-wise Spare % hai (ProductionOrderLine.allowance_percent).
import math
from decimal import ROUND_HALF_UP, Decimal

MAX_EXTRA_PERCENT = 50


def is_kg_product(product):
    unit = (product.base_unit.code if product and product.base_unit else "KG").upper()
    return unit in ("KG", "KGS")


def planned_with_extra(base_qty, extra_percent, product):
    """Banane wali qty. extra_percent 0 ho to base qty hi (bina round kiye, kyunki customer ki qty jaisi hai waisi)."""
    if not extra_percent:
        return float(base_qty)
    raw = float(base_qty) * (1 + float(extra_percent) / 100)
    if is_kg_product(product):
        # Half-up (JS preview jaisa): Python ka round() tie par even ki taraf jaata hai, isliye Decimal
        return float(Decimal(repr(round(raw, 8))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    return float(math.ceil(round(raw, 6)))


def read_extra_percent(raw):
    """Form ki Extra % value padho. (value, None) ya (None, "error"). Khaali = 0; 0 se 50 tak."""
    raw = (raw or "").strip()
    if not raw:
        return 0.0, None
    try:
        value = float(raw)
    except ValueError:
        return None, "Extra % must be a number."
    if not math.isfinite(value):         # "nan" / "inf" form se aa sakte hain: dono range check se nikal jaate hain
        return None, "Extra % must be a number."
    if value < 0 or value > MAX_EXTRA_PERCENT:
        return None, f"Extra % must be between 0 and {MAX_EXTRA_PERCENT}."
    return round(value, 2), None
