# Bill post / cancel hone par paisa kahan jaata hai: SIRF isi file me likha hai.
#
# Abhi sirf vendor ka ledger badalta hai. Jab Inventory (stock ledger) aur Accounting (vouchers: Dr/Cr entries)
# banenge, to unka asar bhi yahin judega: baaki code (routes) ko kuch badalna nahi padega.
#
# Project ka sign rule (memory.md): Ledger.current_balance me  Cr = plus (+),  Dr = minus (-).
# Vendor ko paisa DENA hai => Cr => balance plus ki taraf badhta hai.


def post_invoice(invoice):
    # Draft bill ko Posted banao: vendor ko dena baaki (Cr) total_amount se badhta hai.
    ledger = invoice.vendor.ledger
    ledger.current_balance = round(ledger.current_balance + invoice.total_amount, 2)
    invoice.status = "Posted"


def cancel_invoice(invoice):
    # Bill cancel karo. Posted tha to ledger ka asar wapas (reverse); Draft ka ledger par koi asar hua hi nahi tha.
    # Cancelled bill ki quantity apne aap wapas khul jaati hai (GRNLine.billed_qty Cancelled ko ginta hi nahi).
    if invoice.status == "Posted":
        ledger = invoice.vendor.ledger
        ledger.current_balance = round(ledger.current_balance - invoice.total_amount, 2)
    invoice.status = "Cancelled"

def post_return(purchase_return):
    # Return post karo: vendor ka payable total_amount se GHATTA hai (Dr = minus, bill ke ulta).
    # total_amount me goods + GST + charges (Add / Minus) sab aa chuka hai, route use pehle nikal deta hai.
    ledger = purchase_return.invoice.vendor.ledger
    ledger.current_balance =  round(ledger.current_balance - purchase_return.total_amount, 2)
    purchase_return.status = "Posted"

def cancel_return(purchase_return):
    # Return cancel karo: ledger ka asar wapas (reverse). Sirf Posted par; pehle se Cancelled par dobara nahi.
    if purchase_return.status == "Posted":
        ledger = purchase_return.invoice.vendor.ledger
        ledger.current_balance = round(ledger.current_balance + purchase_return.total_amount, 2)
    purchase_return.status = "Cancelled"