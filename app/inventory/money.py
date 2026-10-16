# Stock ke paise / qty ka hisaab: Decimal se (float ki 0.1 + 0.2 galti se bachne ke liye), round half-up.
# Qty 4 decimal tak, paisa 2 decimal tak. Database me Float rakhte hain, par jodna-ghatana yahin ke helpers se.
from decimal import Decimal, ROUND_HALF_UP


def _d(value):
    # float ko seedha Decimal(float) mat karo — str ke through lo
    return Decimal(str(value or 0))


def q2(value):
    return float(_d(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def q4(value):
    return float(_d(value).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def value_for_out(remaining_qty, remaining_value, qty_out):
    """Lot ka kuch hissa bahar jaye to uski value. Poora bacha hua maal nikle to poori bachi hui value
    (paise ka tukda bachta nahi); warna bachi value ka anupaat (remaining_value x qty_out / remaining_qty)."""
    remaining_qty = q4(remaining_qty)
    qty_out = q4(qty_out)
    if remaining_qty <= 0:
        return 0.0
    if qty_out >= remaining_qty:
        return q2(remaining_value)
    return q2(_d(remaining_value) * _d(qty_out) / _d(remaining_qty))
