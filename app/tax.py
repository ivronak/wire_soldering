# GST ka ek hi hisaab — PO, Purchase Invoice aur Purchase Return teeno yahi use karenge (F9, client rule).
# Rule: charges (freight, packing...) bhi taxable value me judte hain, aur GST items + charges ke total par lagta hai.
# Alag-alag GST rate wali lines ho to charge ko lines me unki value ke anupaat me baant dete hain,
# aur har line apne rate se tax deti hai (isse 5% aur 18% ki lines ka freight bhi sahi rate me bantta hai).
# Paise ka hisaab Decimal se (0.1 + 0.2 wali float galti se bachne ke liye), result round-2 float me.
from decimal import Decimal, ROUND_HALF_UP

TWO = Decimal("0.01")


def _d(value):
    # float ko seedha Decimal(float) mat karo — str ke through lo, warna 0.1 = 0.1000000000000000055...
    return Decimal(str(value or 0))


def _q2(value):
    return value.quantize(TWO, rounding=ROUND_HALF_UP)


def line_value(qty, rate):
    # Line ki value = qty x rate, paise tak round (half-up). PO / bill / return teeno me line yahi se banti hai,
    # taaki screen (JS) aur server ka total ek hi aaye.
    return float(_q2(_d(qty) * _d(rate)))


def split_tax(tax_amount):
    # Intra-state bill me tax aadha CGST aur aadha SGST hota hai. Paisa bachna nahi chahiye,
    # isliye CGST round karo aur SGST = baaki (dono ka jod hamesha poora tax).
    tax = _d(tax_amount)
    cgst = _q2(tax / 2)
    return float(cgst), float(tax - cgst)


def calc_tax(lines, charges_net=0):
    """lines: list of (value, rate_percent) — value = qty x rate (tax se pehle).
    charges_net: charges ka net (Add ka jod - Minus ka jod), tax se pehle.
    Return: dict — items_total, charges_net, taxable_total, tax_total, grand_total,
    lines (har line ka value / charge_share / taxable / rate / tax), by_rate ({rate: {taxable, tax}})."""
    values = [_d(value) for value, _rate in lines]
    rates = [_d(rate) for _value, rate in lines]
    items_total = sum(values, Decimal("0"))
    net = _q2(_d(charges_net))

    # Charge ka hissa har line ko value ke anupaat me; aakhri line ko "baaki" taaki hisse ka jod = poora charge
    shares = []
    given = Decimal("0")
    for index, value in enumerate(values):
        if items_total == 0:
            share = Decimal("0")
        elif index == len(values) - 1:
            share = net - given
        else:
            share = _q2(net * value / items_total)
        given += share
        shares.append(share)

    out_lines = []
    by_rate = {}
    tax_total = Decimal("0")
    for value, rate, share in zip(values, rates, shares):
        taxable = value + share
        tax = _q2(taxable * rate / 100)
        tax_total += tax
        out_lines.append({"value": float(value), "charge_share": float(share), "taxable": float(taxable),
                          "rate": float(rate), "tax": float(tax)})
        slab = by_rate.setdefault(float(rate), {"taxable": Decimal("0"), "tax": Decimal("0")})
        slab["taxable"] += taxable
        slab["tax"] += tax

    taxable_total = items_total + net
    return {
        "items_total": float(_q2(items_total)),
        "charges_net": float(net),
        "taxable_total": float(_q2(taxable_total)),
        "tax_total": float(tax_total),
        "grand_total": float(_q2(taxable_total + tax_total)),
        "lines": out_lines,
        "by_rate": {rate: {"taxable": float(_q2(v["taxable"])), "tax": float(v["tax"])} for rate, v in by_rate.items()},
    }
