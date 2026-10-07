from app.extensions import db
from datetime import datetime

class Unit(db.Model):
    #Table name SQL me "units" hoga
    __tablename__ = "units"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    is_base_unit = db.Column(db.Boolean, default=False, nullable=False)
    #soft-delete : True : In Use, False : Stopped (hard delete nahi)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

class Machines(db.Model):
    __tablename__ = "machines"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    work_stage_id = db.Column(db.Integer, db.ForeignKey("work_stage.id"), nullable=False)
    work_stage = db.relationship("WorkStage")
    capacity = db.Column(db.String(50), nullable=True)
    installed_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), default="active", nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

class WorkStage(db.Model):
    __tablename__="work_stage"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False) 
    name = db.Column(db.String(100), nullable=False)
    #  Chhota number = pehle stage (cutting=10, soldering=20...)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

class RmCategories(db.Model):
    __tablename__='rm_categories'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

class RawMaterial(db.Model):
    __tablename__ = "raw_materials"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=True)

    # FKs - From Dropdown 
    category_id = db.Column(db.Integer, db.ForeignKey('rm_categories.id'), nullable=False)
    base_unit_id = db.Column(db.Integer, db.ForeignKey('units.id'), nullable=False)
    alt_unit_id = db.Column(db.Integer, db.ForeignKey('units.id'), nullable=True)
    tax_rate_id = db.Column(db.Integer, db.ForeignKey("tax_rates.id"), nullable=True)

    category = db.relationship("RmCategories", foreign_keys=[category_id])
    base_unit = db.relationship("Unit", foreign_keys=[base_unit_id])
    alt_unit = db.relationship("Unit", foreign_keys=[alt_unit_id])
    tax_rate = db.relationship("TaxRate", foreign_keys=[tax_rate_id])

    # Recipe form ke dropdown ke liye — dono optional, default off
    is_base_metal = db.Column(db.Boolean, default=False, nullable=False)
    is_core_flux = db.Column(db.Boolean, default=False, nullable=False)

    conversion_note = db.Column(db.String(100), nullable=True)
    reorder_level = db.Column(db.Integer, nullable=True)
    min_stock = db.Column(db.Integer, nullable=True)
    max_stock = db.Column(db.Integer, nullable=True)
    hsn_code = db.Column(db.String(8), nullable=True)

    valuation_method = db.Column(db.String(20), default='fifo', nullable=False)

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

class TaxRate(db.Model):
    __tablename__ = 'tax_rates'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    label = db.Column(db.String(100), nullable=False)
    rate_percent = db.Column(db.Float, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    


class ProductCategories(db.Model):
    __tablename__ = "product_categories"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    attribute_fields = db.Column(db.JSON, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False )
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    attributes = db.Column(db.JSON, nullable=True)

    category_id = db.Column(db.Integer, db.ForeignKey("product_categories.id"), nullable=False)
    base_unit_id = db.Column(db.Integer, db.ForeignKey("units.id"), nullable=False)

    category = db.relationship("ProductCategories", foreign_keys=[category_id])
    base_unit = db.relationship("Unit", foreign_keys=[base_unit_id])

    hsn_code = db.Column(db.String(8), nullable=True)
    tax_rate_id = db.Column(db.Integer, db.ForeignKey("tax_rates.id"), nullable=False)
    tax_rate = db.relationship("TaxRate", foreign_keys=[tax_rate_id])

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

    @property
    def active_variants(self):
        return [v for v in self.variants if not v.is_deleted]

class ProductVariant(db.Model):
    __tablename__ = "product_variants" 

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    product = db.relationship("Product", foreign_keys=[product_id], backref="variants")

    name = db.Column(db.String(100), nullable=False)
    sku = db.Column(db.String(30), unique=True, nullable=False)
    attributes = db.Column(db.JSON, nullable=True)
    min_selling_price = db.Column(db.Float, nullable=True)

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

class VariantRecipeItem(db.Model):
    __tablename__ = "variant_recipe_items"

    id = db.Column(db.Integer, primary_key=True)
    variant_id = db.Column(db.Integer, db.ForeignKey("product_variants.id"), nullable=True)
    variant = db.relationship("ProductVariant", foreign_keys=[variant_id], backref="recipe_items")

    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    product = db.relationship("Product", foreign_keys=[product_id], backref="recipe_items")
    
    raw_material_id = db.Column(db.Integer, db.ForeignKey("raw_materials.id"), nullable=False)
    raw_material = db.relationship("RawMaterial", foreign_keys=[raw_material_id])

    ratio_percent = db.Column(db.Float, nullable=False)
    is_flux = db.Column(db.Boolean, default=False, nullable=False)
    

class Branch(db.Model):
    __tablename__ = "branches"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    # State ab State Master (states table) se FK hai — hardcoded list se nahi
    state_id = db.Column(db.Integer, db.ForeignKey("states.id"), nullable=False)
    state = db.relationship("State", foreign_keys=[state_id])
    gstin = db.Column(db.String(15), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

class Warehouse(db.Model):
    __tablename__ = "warehouses"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    warehouse_type = db.Column(db.String(20), nullable=False)

    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=False)
    branch = db.relationship("Branch", foreign_keys=[branch_id])

    location = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

class ChartOfAccountsGroup(db.Model):
    __tablename__ = "chart_of_accounts_groups"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    classification = db.Column(db.String(20), nullable=False)

class Ledger(db.Model):
    __tablename__ = "ledgers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

    group_id = db.Column(db.Integer, db.ForeignKey("chart_of_accounts_groups.id"), nullable=False)
    group = db.relationship("ChartOfAccountsGroup", foreign_keys=[group_id])

    opening_balance = db.Column(db.Float, default=0, nullable=False)
    opening_balance_type = db.Column(db.String(2), default="Cr", nullable=False)
    current_balance = db.Column(db.Float, default=0, nullable=False)
    gstin = db.Column(db.String(15), nullable=True)

class Vendor(db.Model):
    __tablename__ = "vendors"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)

    contact_person = db.Column(db.String(100), nullable=True)
    mobile = db.Column(db.String(15), nullable=True)
    email = db.Column(db.String(100), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    # State ab State Master (states table) se FK hai — hardcoded list se nahi
    state_id = db.Column(db.Integer, db.ForeignKey("states.id"), nullable=False)
    state = db.relationship("State", foreign_keys=[state_id])

    gstin = db.Column(db.String(15), nullable=True)
    pan = db.Column(db.String(10), nullable=True)

    # Payment terms ab Payment Terms Master (payment_terms table) se FK hai — OPTIONAL (nullable)
    payment_terms_id = db.Column(db.Integer, db.ForeignKey("payment_terms.id"), nullable=True)
    payment_terms = db.relationship("PaymentTerm", foreign_keys=[payment_terms_id])

    bank_name = db.Column(db.String(100), nullable=True)
    bank_ifsc = db.Column(db.String(11), nullable=True)
    bank_account = db.Column(db.String(20), nullable=True)

    # Vendor type ab Vendor Type Master (vendor_types table) se FK hai — OPTIONAL (nullable).
    vendor_type_id = db.Column(db.Integer, db.ForeignKey("vendor_types.id"), nullable=True)
    vendor_type = db.relationship("VendorType", foreign_keys=[vendor_type_id])

    ledger_id = db.Column(db.Integer, db.ForeignKey("ledgers.id"), nullable=False)
    ledger = db.relationship("Ledger", foreign_keys=[ledger_id])

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)


class Customer(db.Model):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)

    contact_person = db.Column(db.String(100), nullable=True)
    mobile = db.Column(db.String(15), nullable=True)
    email = db.Column(db.String(100), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    # State ab State Master (states table) se FK hai — hardcoded list se nahi
    state_id = db.Column(db.Integer, db.ForeignKey("states.id"), nullable=False)
    state = db.relationship("State", foreign_keys=[state_id])
    
    gstin = db.Column(db.String(15), nullable=True)
    pan = db.Column(db.String(10), nullable=True)

    # Payment terms ab Payment Terms Master (payment_terms table) se FK hai — OPTIONAL (nullable)
    payment_terms_id = db.Column(db.Integer, db.ForeignKey("payment_terms.id"), nullable=True)
    payment_terms = db.relationship("PaymentTerm", foreign_keys=[payment_terms_id])
    credit_limit = db.Column(db.Float, nullable=True)

    bank_name = db.Column(db.String(100), nullable=True)
    bank_ifsc = db.Column(db.String(11), nullable=True)
    bank_account = db.Column(db.String(20), nullable=True)

    ledger_id = db.Column(db.Integer, db.ForeignKey("ledgers.id"), nullable=False)
    ledger = db.relationship("Ledger", foreign_keys=[ledger_id])

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

class PurchaseOrder(db.Model):
    __tablename__ = "purchase_orders"

    id = db.Column(db.Integer, primary_key=True)
    po_no = db.Column(db.String(20), unique=True, nullable=False)

    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=False)
    vendor = db.relationship("Vendor", foreign_keys=[vendor_id])

    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=False)
    warehouse = db.relationship("Warehouse", foreign_keys=[warehouse_id])

    po_date = db.Column(db.Date, nullable=False)
    expected_delivery_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), default="Draft", nullable=False)
    remarks = db.Column(db.String(255), nullable=True)

    # Payment terms ab Payment Terms Master (payment_terms table) se FK hai — OPTIONAL (nullable)
    payment_terms_id = db.Column(db.Integer, db.ForeignKey("payment_terms.id"), nullable=True)
    payment_terms = db.relationship("PaymentTerm", foreign_keys=[payment_terms_id])

    freight = db.Column(db.Float, default=0, nullable=False)
    # Confirm karte waqt vendor ka invoice/bill attach hota hai (§10.5) — sab optional
    vendor_invoice_no = db.Column(db.String(50), nullable=True)
    vendor_invoice_date = db.Column(db.Date, nullable=True)
    vendor_invoice_file = db.Column(db.String(255), nullable=True)

    # Short Close karte waqt reason yahan store hota hai (§10.7) — PO ko manually
    # "aur GRN nahi aayega" mark karna, status "Cancelled" ho jata hai
    short_close_reason = db.Column(db.String(255), nullable=True)


    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

class PurchaseOrderLine(db.Model):
    __tablename__ = "purchase_order_lines"

    id = db.Column(db.Integer, primary_key=True)
    po_id = db.Column(db.Integer, db.ForeignKey("purchase_orders.id"), nullable=False)
    po = db.relationship("PurchaseOrder", foreign_keys=[po_id], backref="lines")

    raw_material_id = db.Column(db.Integer, db.ForeignKey('raw_materials.id'), nullable=False)
    raw_material = db.relationship("RawMaterial", foreign_keys=[raw_material_id])

    ordered_qty = db.Column(db.Float, nullable=False)
    rate = db.Column(db.Float, nullable=False)
    unit_id = db.Column(db.Integer, db.ForeignKey("units.id"), nullable=False)
    unit = db.relationship("Unit", foreign_keys=[unit_id])

    tax_rate_id = db.Column(db.Integer, db.ForeignKey("tax_rates.id"), nullable=False)
    tax_rate = db.relationship("TaxRate", foreign_keys=[tax_rate_id])

    discount_percent = db.Column(db.Float, default=0, nullable=False)
    @property
    def received_qty(self):
        # Sirf Draft se aage badhi GRN Lines count hoti hain - Draft abhi "pakka" nahi he
        total = 0
        for line in self.grn_lines:
            if line.grn.status != "Draft":
                total += line.received_qty
        return total

    @property
    def remaining_qty(self):
        return self.ordered_qty - self.received_qty            

class PurchaseOrderCharge(db.Model):
    __tablename__ = "purchase_order_charges"

    id = db.Column(db.Integer, primary_key=True)
    po_id = db.Column(db.Integer, db.ForeignKey("purchase_orders.id"), nullable=False)
    po = db.relationship("PurchaseOrder", foreign_keys=[po_id], backref="charge_lines")

    charge_id = db.Column(db.Integer, db.ForeignKey('charges.id'), nullable=False)  
    charge = db.relationship("Charge", foreign_keys=[charge_id])

    amount = db.Column(db.Float, nullable=False)
    # "add" total mein judta hai. "minus" total se katta hai.
    effect = db.Column(db.String(10), nullable=False)  

class GRN(db.Model):
    __tablename__="grns"

    id = db.Column(db.Integer, primary_key=True)
    grn_no = db.Column(db.String(20), unique=True, nullable=False)

    po_id = db.Column(db.Integer, db.ForeignKey("purchase_orders.id"), nullable=False)
    po = db.relationship("PurchaseOrder", foreign_keys=[po_id], backref="grns")

    grn_date = db.Column(db.Date, nullable=False)
    challan_no = db.Column(db.String(50), nullable=True)
    transporter = db.Column(db.String(100), nullable=True)
    vehicle_no = db.Column(db.String(20), nullable=True)
    gross_weight = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(20), default="Pending QC", nullable=False)
    remarks = db.Column(db.String(255), nullable=True)

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

class GRNLine(db.Model):
    __tablename__ = "grn_lines"

    id = db.Column(db.Integer, primary_key=True)
    grn_id = db.Column(db.Integer, db.ForeignKey("grns.id"), nullable=False)
    grn = db.relationship("GRN", foreign_keys=[grn_id], backref="lines")

    po_line_id = db.Column(db.Integer, db.ForeignKey("purchase_order_lines.id"), nullable=False)
    po_line = db.relationship("PurchaseOrderLine", foreign_keys=[po_line_id], backref='grn_lines')

    received_qty = db.Column(db.Float, nullable=False)
    batch_lot_no = db.Column(db.String(30), nullable=False)
    mfg_date = db.Column(db.Date, nullable=True)

class InwardQC(db.Model):
    # Ek QC = ek GRN line (material + batch/lot) ki inspection
    __tablename__ = "inward_qc"

    id = db.Column(db.Integer, primary_key=True)
    qc_no = db.Column(db.String(20), unique=True, nullable=False)

    # Poori GRN nahi — uski ek line
    grn_line_id = db.Column(db.Integer, db.ForeignKey("grn_lines.id"), nullable=False)
    grn_line = db.relationship("GRNLine", foreign_keys=[grn_line_id])

    inspection_date = db.Column(db.Date, nullable=False)
    # Auth/User master baad me — abhi naam text
    inspector = db.Column(db.String(100), nullable=False)

    sample_size = db.Column(db.Float, nullable=False)
    passed_qty = db.Column(db.Float, nullable=False)
    rejected_qty = db.Column(db.Float, nullable=False)

    # Draft / Passed / Partial / Failed
    status = db.Column(db.String(20), default="Draft", nullable=False)
    remarks = db.Column(db.String(255), nullable=True)

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

class Charge(db.Model):
    __tablename__ = 'charges'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_deleted = db.Column(db.Boolean, default=False)

class State(db.Model):
    # State / UT master. GST state code yahin se aayega (CGST+SGST vs IGST decide karne ke liye)
    __tablename__ = "states"

    id = db.Column(db.Integer, primary_key=True)
    # Auto serial (Charges jaisa) - route generate karta hai, form se nahi aata
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    # Government code (Gujarat = 24). String(2) isliye ki 01/02 ka leading zero na ude.
    # DB level pe unique nahi - duplicate check route me hota hai (soft-delete + restore flow ke liye)
    gst_state_code = db.Column(db.String(2), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)


class VendorType(db.Model):
    # Vendor Type master — Vendor form ke "Vendor type" dropdown ki source.
    # Pehle ye dropdown hardcoded tha (5 options). Ab ye master table hai, aur
    # migration me wahi purane 5 options seed kiye gaye hain.
    # Vendor.vendor_type_id isse link hoga (OPTIONAL / nullable FK).
    __tablename__ = "vendor_types"

    id = db.Column(db.Integer, primary_key=True)
    # Auto serial (Charges / State jaisa) — route generate karta hai, form se nahi aata
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)


class ProductionOrder(db.Model):
    # Finished product banane ka order. Recipe yahan copy hoti hai, product master se live nahi judti.
    __tablename__ = "production_orders"

    id = db.Column(db.Integer, primary_key=True)
    prod_no = db.Column(db.String(20), unique=True, nullable=False)

    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    product = db.relationship("Product", foreign_keys=[product_id])

    order_date = db.Column(db.Date, nullable=False)
    planned_qty = db.Column(db.Float, nullable=False)
    # KG product pe 1. Doosri unit pe ek piece ka weight, taaki batch KG nikal sake.
    unit_weight = db.Column(db.Float, default=1, nullable=False)
    status = db.Column(db.String(20), default="Draft", nullable=False)
    remarks = db.Column(db.String(255), nullable=True)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)


class ProductionOrderLine(db.Model):
    # Us din ki recipe copy: ratio aur required qty. Recipe line ki id yahan nahi.
    __tablename__ = "production_order_lines"

    id = db.Column(db.Integer, primary_key=True)
    production_order_id = db.Column(db.Integer, db.ForeignKey("production_orders.id"), nullable=False)
    production_order = db.relationship("ProductionOrder", foreign_keys=[production_order_id], backref="lines")

    raw_material_id = db.Column(db.Integer, db.ForeignKey("raw_materials.id"), nullable=False)
    raw_material = db.relationship("RawMaterial", foreign_keys=[raw_material_id])

    ratio_percent = db.Column(db.Float, nullable=False)
    required_qty = db.Column(db.Float, nullable=False)
    is_flux = db.Column(db.Boolean, default=False, nullable=False)
    # True = user ne packaging / extra RM add kiya. Ratio nahi, qty seedha type hoti hai.
    is_extra = db.Column(db.Boolean, default=False, nullable=False)


class PaymentTerm(db.Model):
    # Payment Terms master — Vendor / Customer / Purchase order forms ke
    # "Payment terms" dropdown ki source. Pehle ye dropdown 3 jagah hardcoded
    # tha (5 options). Ab ye master table hai, aur migration me wahi purane
    # 5 options seed kiye gaye hain.
    # Vendor.payment_terms_id / Customer.payment_terms_id /
    # PurchaseOrder.payment_terms_id isse link honge (sab OPTIONAL / nullable FK).
    __tablename__ = "payment_terms"

    id = db.Column(db.Integer, primary_key=True)
    # Auto serial (Charges / State / Vendor Type jaisa) — route generate karta hai, form se nahi aata
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)


class PartyDocument(db.Model):
    # Vendor/Customer dono ke uploaded documents (GST cert, PAN, etc.) yahan store hote hain —
    # party_type ("vendor"/"customer") + party_id batata hai kis record ka document hai.
    # Spec §10.4 — ek hi shared table, do alag tables nahi.
    __tablename__ = "party_documents"

    id = db.Column(db.Integer, primary_key=True)
    party_type = db.Column(db.String(20), nullable=False)
    party_id = db.Column(db.Integer, nullable=False)

    document_title = db.Column(db.String(100), nullable=True)
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer, nullable=True)

    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

class RejectionMemo(db.Model):
    __tablename__ = "rejection_memos"

    id = db.Column(db.Integer, primary_key=True)
    memo_no = db.Column(db.String(20), unique=True, nullable=False)

    inward_qc_id = db.Column(db.Integer, db.ForeignKey("inward_qc.id"), unique=True, nullable=False)
    inward_qc = db.relationship("InwardQC", foreign_keys=[inward_qc_id], backref=db.backref("memo", uselist=False))

    memo_date = db.Column(db.Date, nullable=False)
    rejected_qty = db.Column(db.Float, nullable=False)   # snapshot
    reason = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), default="Issued", nullable=False)

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)