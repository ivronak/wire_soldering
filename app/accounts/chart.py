# Accounts A1: starter Chart of Accounts — groups (Tally jaisa tree) + system ledgers. Ye sirf DATA hai; migration isse seed karti hai.
# System group / ledger ko Admin hata ya rename nahi kar sakta (auto-posting inhi par tikti hai, system_key se dhundhti hai).
# "Sundry Debtors" / "Sundry Creditors" pehle se Customer / Vendor form me naam se bante hain (customers/routes.py, vendors/routes.py),
# isliye yahan wahi naam + classification rakhe — migration pehle dekhti hai, hai to naya nahi banati, bas parent jodti hai.
# Sign rule (project): Ledger.current_balance me Cr = plus, Dr = minus.

# (name, classification, parent name)
GROUPS = [
    ("Capital Account", "EQUITY", None),
    ("Reserves & Surplus", "EQUITY", None),
    ("Loans", "LIABILITY", None),
    ("Current Liabilities", "LIABILITY", None),
    ("Sundry Creditors", "LIABILITY", "Current Liabilities"),
    ("Duties & Taxes", "LIABILITY", "Current Liabilities"),
    ("Current Assets", "ASSET", None),
    ("Sundry Debtors", "ASSET", "Current Assets"),
    ("Cash-in-hand", "ASSET", "Current Assets"),
    ("Bank Accounts", "ASSET", "Current Assets"),
    ("Stock-in-hand", "ASSET", "Current Assets"),
    ("Fixed Assets", "ASSET", None),
    ("Sales Accounts", "INCOME", None),
    ("Purchase Accounts", "EXPENSE", None),
    ("Direct Expenses", "EXPENSE", None),
    ("Indirect Expenses", "EXPENSE", None),
]

# (system_key, ledger name, group name)
SYSTEM_LEDGERS = [
    ("sales", "Sales", "Sales Accounts"),
    ("sales_return", "Sales Return", "Sales Accounts"),
    ("sales_charges", "Charges on Sales", "Sales Accounts"),
    ("scrap_sales", "Scrap Sales", "Sales Accounts"),
    ("purchase", "Purchase", "Purchase Accounts"),
    ("purchase_return", "Purchase Return", "Purchase Accounts"),
    ("purchase_charges", "Charges on Purchase", "Purchase Accounts"),
    ("cash", "Cash", "Cash-in-hand"),
    ("stock_in_hand", "Stock-in-hand", "Stock-in-hand"),
    ("cogs", "Cost of Goods Sold", "Direct Expenses"),
    ("round_off", "Round Off", "Indirect Expenses"),
    ("output_cgst", "Output CGST", "Duties & Taxes"),
    ("output_sgst", "Output SGST", "Duties & Taxes"),
    ("output_igst", "Output IGST", "Duties & Taxes"),
    ("input_cgst", "Input CGST", "Duties & Taxes"),
    ("input_sgst", "Input SGST", "Duties & Taxes"),
    ("input_igst", "Input IGST", "Duties & Taxes"),
    # Fixed cost (rent / salary / bijli) jo production ke maal ki cost me judta hai: Dr Stock-in-hand, Cr yeh ledger (abhi dena / chukana baaki)
    ("fixed_cost_payable", "Fixed Cost Payable", "Current Liabilities"),
    # A2 backfill: purane party balances ke opening journal ka doosra taraf
    ("opening_balance", "Opening Balance Adjustment", "Capital Account"),
]
