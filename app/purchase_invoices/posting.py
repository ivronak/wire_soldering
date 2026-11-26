# Bill post / cancel hone par paisa kahan jaata hai: SIRF isi file me likha hai.
#
# Abhi sirf vendor ka ledger badalta hai. Jab Inventory (stock ledger) aur Accounting (vouchers: Dr/Cr entries)
# banenge, to unka asar bhi yahin judega: baaki code (routes) ko kuch badalna nahi padega.
#
# Project ka sign rule (memory.md): Ledger.current_balance me  Cr = plus (+),  Dr = minus (-).
# Vendor ko paisa DENA hai => Cr => balance plus ki taraf badhta hai.


from app.accounts.autopost import SRC_PURCHASE, SRC_PURCHASE_RETURN, post_purchase_invoice, post_purchase_return, reverse_for
from app.auth import service as auth_service
from app.extensions import db
from app.inventory.posting import bill_to_stock, bill_cancelled


def post_invoice(invoice):
    # Draft bill ko Posted banao: vendor ko dena baaki (Cr) total_amount se badhta hai.
    # C5: saath me us bill ke lots ki stock value bill ke final rate par ho jaati hai (qty nahi badalti)
    ledger = invoice.vendor.ledger
    ledger.current_balance = round(ledger.current_balance + invoice.total_amount, 2)
    invoice.status = "Posted"
    bill_to_stock(invoice)
    db.session.flush()
    post_purchase_invoice(invoice, created_by_id=auth_service.actor_id())      # Accounts A4: voucher (Dr Stock + Input GST, Cr Vendor)


def cancel_invoice(invoice):
    # Bill cancel karo. Posted tha to ledger ka asar wapas (reverse); Draft ka ledger par koi asar hua hi nahi tha.
    # Cancelled bill ki quantity apne aap wapas khul jaati hai (GRNLine.billed_qty Cancelled ko ginta hi nahi).
    if invoice.status == "Posted":
        ledger = invoice.vendor.ledger
        ledger.current_balance = round(ledger.current_balance - invoice.total_amount, 2)
        bill_cancelled(invoice)         # C5: lot wapas PO rate (estimate) par
        reverse_for(SRC_PURCHASE, invoice.id, "Bill cancelled", created_by_id=auth_service.actor_id())      # Accounts A4: voucher ulta
    invoice.status = "Cancelled"

from app.inventory.posting import return_to_stock, return_cancelled


def post_return(purchase_return):
    # Return post karo: vendor ka payable total_amount se GHATTA hai (Dr = minus, bill ke ulta).
    # total_amount me goods + GST + charges (Add / Minus) sab aa chuka hai, route use pehle nikal deta hai.
    # Pehle stock se maal nikalo (kam stock ho to InventoryError, kuch save nahi hoga), phir paisa
    return_to_stock(purchase_return)
    ledger = purchase_return.invoice.vendor.ledger
    ledger.current_balance =  round(ledger.current_balance - purchase_return.total_amount, 2)
    purchase_return.status = "Posted"
    db.session.flush()
    post_purchase_return(purchase_return, created_by_id=auth_service.actor_id())      # Accounts A4: debit note voucher

def cancel_return(purchase_return):
    # Return cancel karo: ledger ka asar wapas (reverse). Sirf Posted par; pehle se Cancelled par dobara nahi.
    if purchase_return.status == "Posted":
        return_cancelled(purchase_return)      # stock wapas (ulti rows)
        ledger = purchase_return.invoice.vendor.ledger
        ledger.current_balance = round(ledger.current_balance + purchase_return.total_amount, 2)
        reverse_for(SRC_PURCHASE_RETURN, purchase_return.id, "Debit note cancelled", created_by_id=auth_service.actor_id())      # Accounts A4
    purchase_return.status = "Cancelled"