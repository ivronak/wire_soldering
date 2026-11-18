from sqlalchemy import event, text
from app.extensions import db
from datetime import datetime
from app.timeutil import utc_now
from app.tax import calc_tax, split_tax, line_value

# Har table me "kab banaya" (created_at) khud bhar jaata hai — UTC me; screen par IST me dikhta hai (app/timeutil.py).
# nullable=True kyunki purani rows ka time kisi ko nahi pata — unme khaali rehta hai, jhoothi value nahi bharte.
class CreatedAtMixin:
    created_at = db.Column(db.DateTime, default=utc_now, nullable=True)


class Unit(CreatedAtMixin, db.Model):
    #Table name SQL me "units" hoga
    __tablename__ = "units"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    is_base_unit = db.Column(db.Boolean, default=False, nullable=False)
    #soft-delete : True : In Use, False : Stopped (hard delete nahi)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

class ProductionLine(CreatedAtMixin, db.Model):
    # Production Line (Line 1, Line 2 ...): 8 stages ka poora set + apni machines + daily capacity (KG/din). Client change #1.
    # Machine sirf ek line me hoti hai (machines.line_id). Order ko line dena queue -> process ke time hoga.
    __tablename__ = "production_lines"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    daily_capacity_kg = db.Column(db.Float, nullable=False)
    handler = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

    @property
    def active_machines(self):
        # Is line ki machines jo list se hati nahi (retired bhi dikhti hain, delete hui nahi)
        return [m for m in self.machines if not m.is_deleted]


class Machines(CreatedAtMixin, db.Model):
    __tablename__ = "machines"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    work_stage_id = db.Column(db.Integer, db.ForeignKey("work_stage.id"), nullable=False)
    work_stage = db.relationship("WorkStage")
    # Machine kis production line ki hai (ek hi line). Khaali = abhi kisi line me nahi lagi.
    line_id = db.Column(db.Integer, db.ForeignKey("production_lines.id"), nullable=True)
    line = db.relationship("ProductionLine", foreign_keys=[line_id], backref="machines")
    # Purana text capacity ("500 units/hr") — dikhane ke liye bacha hai. Hisaab ab neeche ke numbers se hota hai.
    capacity = db.Column(db.String(50), nullable=True)
    # Numeric capacity: ek ghante me kitna bana sakti hai (unit Unit Master se, jaise KG) aur din me kitne ghante chalti hai.
    # Production Order ka plan (kitne ghante / din lagenge) isi se nikalta hai.
    capacity_per_hour = db.Column(db.Float, nullable=True)
    capacity_unit_id = db.Column(db.Integer, db.ForeignKey("units.id"), nullable=True)
    capacity_unit = db.relationship("Unit", foreign_keys=[capacity_unit_id])
    hours_per_day = db.Column(db.Float, default=8, server_default="8", nullable=False)
    # C8a: batch machine (furnace / mixer: Work stage me "Batch stage" tick) ke liye: ek melt me kitna (capacity_unit me, jaise KG) aur ek batch me kitne ghante.
    # Per-hour rate (capacity_per_hour) tab apne aap = batch_capacity_kg / hours_per_batch — isliye scheduler ko kuch badalna nahi padta.
    batch_capacity_kg = db.Column(db.Float, nullable=True)
    hours_per_batch = db.Column(db.Float, nullable=True)
    installed_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), default="active", nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

    @property
    def capacity_text(self):
        # Screen par: "120 KG/hr · 8 h/day". Numeric nahi bhara to purana text. Batch machine: "500 KG per batch · 5 h per batch · 8 h/day"
        if self.batch_capacity_kg and self.hours_per_batch:
            unit = self.capacity_unit.code if self.capacity_unit else ""
            return f"{self.batch_capacity_kg:g} {unit} per batch · {self.hours_per_batch:g} h per batch · {self.hours_per_day:g} h/day"
        if self.capacity_per_hour:
            unit = self.capacity_unit.code if self.capacity_unit else ""
            return f"{self.capacity_per_hour:g} {unit}/hr · {self.hours_per_day:g} h/day"
        return self.capacity or "—"

    @property
    def daily_capacity(self):
        # Ek din me kitna (capacity per hour x ghante); numeric na ho to None
        if not self.capacity_per_hour:
            return None
        return round(self.capacity_per_hour * (self.hours_per_day or 0), 4)

class WorkStage(CreatedAtMixin, db.Model):
    __tablename__="work_stage"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False) 
    name = db.Column(db.String(100), nullable=False)
    #  Chhota number = pehle stage (cutting=10, soldering=20...)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    # Batch stage (jaise Melting / furnace): order ek saath nahi, machine ki capacity ke hisaab se lots me jaata hai (client change #6)
    is_batch = db.Column(db.Boolean, default=False, server_default=db.false(), nullable=False)
    # Is stage ke baad Lab QC + Test Certificate (TC) zaroori: TC upload hue bina agla stage start nahi hota (client change #7)
    requires_lab_qc = db.Column(db.Boolean, default=False, server_default=db.false(), nullable=False)
    # Is stage (jaise Melting) ka scrap abhi nahi likhte: kadhai khali hone par agle stage (Ingot Casting) ke complete par likhte hain (client change #8)
    scrap_after_next = db.Column(db.Boolean, default=False, server_default=db.false(), nullable=False)
    # Ingot Casting jaisa stage (client meeting 2, #13): scrap likhne ki jagah operator "kitne lattha (billet) bane" likhta hai;
    # scrap = aaya maal - (lattha x billet_weight) apne aap. billet_weight (KG) yahin ek baar saved rehta hai, complete form me badal sakte hain.
    is_billet_stage = db.Column(db.Boolean, default=False, server_default=db.false(), nullable=False)
    billet_weight = db.Column(db.Float, nullable=True)
    # Is stage me scrap hota hi nahi (Extrusion, Wire Drawing): complete form me scrap box nahi aata, scrap hamesha 0
    no_scrap = db.Column(db.Boolean, default=False, server_default=db.false(), nullable=False)
    # C15: is stage (Spooling) par maal ki ginti PCS me ho jaati hai (spool = pieces). Iske baad ke stages (Testing, Packing) PCS me chalte hain,
    # KG sirf reference. Sirf PCS wale product me lagu; KG product (jaise Flux) me kuch nahi badalta.
    counts_pcs = db.Column(db.Boolean, default=False, server_default=db.false(), nullable=False)
    # C12: is stage (Melting) ke complete hone ke baad agla stage (Ingot Casting) itni minute ke andar shuru hona chahiye, warna garam maal thanda hota hai.
    # Khaali = koi limit nahi. Limit paar ho to agla stage Start karte waqt wajah likhni padti hai (stage notes me jaati hai).
    max_wait_minutes = db.Column(db.Integer, nullable=True)

class RmCategories(CreatedAtMixin, db.Model):
    __tablename__='rm_categories'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

class RawMaterial(CreatedAtMixin, db.Model):
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
    # Packing material (spool, sleeve, box): product ke "Packing Material" section ke dropdown ke liye (client change #2, 2026-10-26)
    is_packing = db.Column(db.Boolean, default=False, nullable=False)

    conversion_note = db.Column(db.String(100), nullable=True)
    reorder_level = db.Column(db.Integer, nullable=True)
    min_stock = db.Column(db.Integer, nullable=True)
    max_stock = db.Column(db.Integer, nullable=True)
    hsn_code = db.Column(db.String(8), nullable=True)

    valuation_method = db.Column(db.String(20), default='fifo', nullable=False)

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

class TaxRate(CreatedAtMixin, db.Model):
    __tablename__ = 'tax_rates'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    label = db.Column(db.String(100), nullable=False)
    rate_percent = db.Column(db.Float, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    


class ProductCategories(CreatedAtMixin, db.Model):
    __tablename__ = "product_categories"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    attribute_fields = db.Column(db.JSON, nullable=True)
    # Flat icon ka key (app/icons.py). Is category ke har product ke saath wahi icon dikhta hai (Finished goods, Product master). Khaali = default.
    icon = db.Column(db.String(30), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

class Product(CreatedAtMixin, db.Model):
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

    # Finished goods ke alert (client change #10): total FG qty min se kam ho to "Below minimum", max se zyada ho to "Overstock". Khaali = alert nahi.
    min_stock = db.Column(db.Integer, nullable=True)
    max_stock = db.Column(db.Integer, nullable=True)

    # 1 piece (spool / roll) ka KG me weight — product ki unit KG na ho tabhi bhari jaati hai (client meeting 2, #4).
    # Order form me ye box nahi aata: qty x unit_weight = KG seedha is se banta hai. Khaali = KG wala product.
    unit_weight = db.Column(db.Float, nullable=True)

    # In-house semi-finished product (jaise Flux): iska output FG me nahi, is Raw Material ke stock me jaata hai, taaki dusre product ki recipe me
    # wo material ban ke issue ho (client meeting 2, #9). Khaali = normal product (output FG me).
    output_rm_id = db.Column(db.Integer, db.ForeignKey("raw_materials.id"), nullable=True)
    output_rm = db.relationship("RawMaterial", foreign_keys=[output_rm_id])

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

    @property
    def active_variants(self):
        return [v for v in self.variants if not v.is_deleted]

    @property
    def routing_stage_ids(self):
        # Is product ke default production stages (ids). Order stage master ke sort_order se aata hai.
        return [row.work_stage_id for row in self.routing_stages]

class ProductVariant(CreatedAtMixin, db.Model):
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

class VariantRecipeItem(CreatedAtMixin, db.Model):
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
    # Ye material kis stage me daalna hai (Flux -> Flux Preparation, Tin / Lead -> Melting). Khaali = kisi khaas stage se bandha nahi.
    work_stage_id = db.Column(db.Integer, db.ForeignKey("work_stage.id"), nullable=True)
    work_stage = db.relationship("WorkStage", foreign_keys=[work_stage_id])
    # Is material ka spare % (wastage ke liye extra, 0-100). Product me ek baar set hota hai; order banate waqt har line par copy hota hai
    spare_percent = db.Column(db.Float, default=0, server_default="0", nullable=False)


class ProductPackingItem(CreatedAtMixin, db.Model):
    # Product ka Packing Material: "har kg_per_pack KG tayyar maal ke liye 1 pack" (1 KG spool -> 1, 20 KG box -> 20).
    # Production order banate waqt ye lines order par copy hoti hain: qty = order KG / kg_per_pack (upar round).
    __tablename__ = "product_packing_items"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    product = db.relationship("Product", foreign_keys=[product_id], backref="packing_items")

    raw_material_id = db.Column(db.Integer, db.ForeignKey("raw_materials.id"), nullable=False)
    raw_material = db.relationship("RawMaterial", foreign_keys=[raw_material_id])

    kg_per_pack = db.Column(db.Float, nullable=False)
    # Ye packing material kis stage me lagta hai (spool -> Spooling, box / sleeve -> Packing). Khaali = kisi stage se bandha nahi.
    work_stage_id = db.Column(db.Integer, db.ForeignKey("work_stage.id"), nullable=True)
    work_stage = db.relationship("WorkStage", foreign_keys=[work_stage_id])
    spare_percent = db.Column(db.Float, default=0, server_default="0", nullable=False)       # recipe jaisa: product me ek baar, order line par copy


class Branch(CreatedAtMixin, db.Model):
    __tablename__ = "branches"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    # State ab State Master (states table) se FK hai — hardcoded list se nahi
    state_id = db.Column(db.Integer, db.ForeignKey("states.id"), nullable=False)
    state = db.relationship("State", foreign_keys=[state_id])
    gstin = db.Column(db.String(15), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

class Warehouse(CreatedAtMixin, db.Model):
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

class ChartOfAccountsGroup(CreatedAtMixin, db.Model):
    __tablename__ = "chart_of_accounts_groups"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    classification = db.Column(db.String(20), nullable=False)

class Ledger(CreatedAtMixin, db.Model):
    __tablename__ = "ledgers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

    group_id = db.Column(db.Integer, db.ForeignKey("chart_of_accounts_groups.id"), nullable=False)
    group = db.relationship("ChartOfAccountsGroup", foreign_keys=[group_id])

    opening_balance = db.Column(db.Float, default=0, nullable=False)
    opening_balance_type = db.Column(db.String(2), default="Cr", nullable=False)
    current_balance = db.Column(db.Float, default=0, nullable=False)
    gstin = db.Column(db.String(15), nullable=True)

class Vendor(CreatedAtMixin, db.Model):
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

    # Order dene se maal aane tak ke din (client change #3: 15-20 din). Material plan "PO kab tak dalo" isi se nikalta hai. Khaali = pata nahi.
    lead_time_days = db.Column(db.Integer, nullable=True)

    # Supplier grade A / B / C (client meeting 2, change 7): Grade A = pasandida (shortlisted) supplier. Khaali = abhi grade nahi diya.
    # 30-day material plan se Draft PO banate waqt Grade A vendors pehle suggest honge.
    grade = db.Column(db.String(1), nullable=True)

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)


class Customer(CreatedAtMixin, db.Model):
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

class PurchaseOrder(CreatedAtMixin, db.Model):
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

    # F9: nayi PO me GST charges + items ke total par lagta hai (True). Purani PO (jo vendor ko ja chuki) ka total
    # na badle, isliye unme server_default False — wahi purana line-wise GST aur charges bina tax ke.
    gst_on_charges = db.Column(db.Boolean, default=True, server_default=db.false(), nullable=False)

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

    @property
    def is_inter_state(self):
        # Vendor ka state aur warehouse ki branch ka state alag ho to IGST, warna CGST + SGST
        vendor_state = self.vendor.state if self.vendor else None
        branch = self.warehouse.branch if self.warehouse else None
        branch_state = branch.state if branch else None
        if vendor_state and branch_state and vendor_state.name == branch_state.name:
            return False
        return True

    @property
    def charge_rows(self):
        # Charges ki list (naam, amount, add / minus). Purani PO me alag charge line nahi, sirf freight column tha.
        rows = []
        for charge_line in self.charge_lines:
            rows.append({"name": charge_line.charge.name if charge_line.charge else "Charge",
                         "amount": charge_line.amount, "effect": charge_line.effect})
        if not self.charge_lines and self.freight:
            rows.append({"name": "Freight", "amount": self.freight, "effect": "add"})
        return rows

    @property
    def summary(self):
        # PO ka poora hisaab ek jagah (print, View, docket sab yahi use karte hain) — app/tax.py ke calc_tax se.
        tax_lines = []
        for line in self.lines:
            percent = line.tax_rate.rate_percent if line.tax_rate else 0
            tax_lines.append((line_value(line.ordered_qty or 0, line.rate or 0), percent))
        net = 0
        for row in self.charge_rows:
            net += -row["amount"] if row["effect"] == "minus" else row["amount"]
        net = round(net, 2)

        if self.gst_on_charges:
            result = calc_tax(tax_lines, net)
        else:
            # Purani PO: tax sirf items par, charges bina tax ke upar se jode / ghataye
            result = calc_tax(tax_lines, 0)
            result["charges_net"] = net
            result["grand_total"] = round(result["grand_total"] + net, 2)
        result["cgst"], result["sgst"] = split_tax(result["tax_total"])
        result["inter"] = self.is_inter_state
        result["gst_on_charges"] = bool(self.gst_on_charges)
        result["charge_rows"] = self.charge_rows
        return result

    @property
    def edit_data(self):
        # Confirm panel me "vendor ne kuch badla ho to yahin theek karo" ke liye — lines aur charges ki abhi ki values
        lines = []
        for line in self.lines:
            material = line.raw_material
            lines.append({"id": line.id,
                          "name": (material.code + " — " + material.name) if material else "Item",
                          "unit": line.unit.code if line.unit else "",
                          "qty": line.ordered_qty, "rate": line.rate, "tax_rate_id": line.tax_rate_id})
        charges = []
        for charge_line in self.charge_lines:
            charges.append({"id": charge_line.id,
                            "name": charge_line.charge.name if charge_line.charge else "Charge",
                            "amount": charge_line.amount, "effect": charge_line.effect})
        return {"lines": lines, "charges": charges, "inter": self.is_inter_state}

    @property
    def revision_data(self):
        from app.timeutil import format_ist
        return [{"when": format_ist(revision.created_at), "note": revision.note} for revision in self.revisions]

class PurchaseOrderLine(CreatedAtMixin, db.Model):
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

class PurchaseOrderCharge(CreatedAtMixin, db.Model):
    __tablename__ = "purchase_order_charges"

    id = db.Column(db.Integer, primary_key=True)
    po_id = db.Column(db.Integer, db.ForeignKey("purchase_orders.id"), nullable=False)
    po = db.relationship("PurchaseOrder", foreign_keys=[po_id], backref="charge_lines")

    charge_id = db.Column(db.Integer, db.ForeignKey('charges.id'), nullable=False)  
    charge = db.relationship("Charge", foreign_keys=[charge_id])

    amount = db.Column(db.Float, nullable=False)
    # "add" total mein judta hai. "minus" total se katta hai.
    effect = db.Column(db.String(10), nullable=False)  

class PurchaseOrderRevision(CreatedAtMixin, db.Model):
    # F10: PO confirm karte waqt vendor ke kehne par rate / qty / tax / charge badle to purana -> naya yahan likha rehta hai.
    __tablename__ = "purchase_order_revisions"

    id = db.Column(db.Integer, primary_key=True)
    po_id = db.Column(db.Integer, db.ForeignKey("purchase_orders.id"), nullable=False)
    po = db.relationship("PurchaseOrder", foreign_keys=[po_id], backref="revisions")
    note = db.Column(db.Text, nullable=False)

class GRN(CreatedAtMixin, db.Model):
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

# GRN ke bill ka helper (neeche GRN class me jodna mushkil hai kyunki GRN pehle define hai, isliye alag function)
def _grn_billing_invoice(grn):
    # Is GRN ka chalta hua bill (Draft ya Posted). Cancelled / remove kiya hua nahi ginte. Nahi hai to None.
    # Purane bills GRN ke lots se jude the (grn_id nahi tha), isliye lines ke raaste dhoondte hain.
    for line in grn.lines:
        for invoice_line in line.invoice_lines:
            invoice = invoice_line.invoice
            if invoice.is_deleted or invoice.status == "Cancelled":
                continue
            return invoice
    return None


def _grn_billing_data(grn):
    # "Create bill" panel (JS) ke liye: is GRN ki saari lines, PO ka rate + tax, aur QC ka result
    po = grn.po
    branch = po.warehouse.branch if po and po.warehouse else None
    tax_type = "intra" if (po and branch and po.vendor and po.vendor.state_id == branch.state_id) else "inter"
    lines = []
    for grn_line in grn.lines:
        po_line = grn_line.po_line
        material = po_line.raw_material if po_line else None
        qc = grn_line.final_qc
        lines.append({
            "id": grn_line.id,
            "material": (material.code + " " + material.name) if material else "",
            "lot": grn_line.batch_lot_no,
            "unit": po_line.unit.code if po_line and po_line.unit else "",
            "received": grn_line.received_qty,
            "passed": qc.passed_qty if qc else 0,
            "rejected": qc.rejected_qty if qc else 0,
            "rate": po_line.rate if po_line else 0,
            "tax_id": po_line.tax_rate_id if po_line else None,
        })
    return {"grn_id": grn.id, "grn_no": grn.grn_no, "po_no": po.po_no if po else "",
            "vendor": po.vendor.name if po and po.vendor else "", "tax_type": tax_type, "lines": lines}


# GRN class upar bani hai; usme ye do property yahin se jodte hain (GRN.billing_invoice / GRN.billing_data)
GRN.billing_invoice = property(_grn_billing_invoice)
GRN.billing_data = property(_grn_billing_data)


class GRNLine(CreatedAtMixin, db.Model):
    __tablename__ = "grn_lines"

    id = db.Column(db.Integer, primary_key=True)
    grn_id = db.Column(db.Integer, db.ForeignKey("grns.id"), nullable=False)
    grn = db.relationship("GRN", foreign_keys=[grn_id], backref="lines")

    po_line_id = db.Column(db.Integer, db.ForeignKey("purchase_order_lines.id"), nullable=False)
    po_line = db.relationship("PurchaseOrderLine", foreign_keys=[po_line_id], backref='grn_lines')

    received_qty = db.Column(db.Float, nullable=False)
    batch_lot_no = db.Column(db.String(30), nullable=False)
    mfg_date = db.Column(db.Date, nullable=True)

    # Rack (client change #10): QC pass hone ke baad maal store warehouse ke is rack me rakha jayega. Optional — purani GRN me khaali.
    # Rack hamesha PO ke store (RM) warehouse ka hota hai (grns/routes.py me jaanch).
    rack_id = db.Column(db.Integer, db.ForeignKey("racks.id"), nullable=True)
    rack = db.relationship("Rack", foreign_keys=[rack_id])

    @property
    def final_qc(self):
        # Is lot ka final QC result (Draft nahi, remove nahi). Nahi hua to None.
        return InwardQC.query.filter(
            InwardQC.grn_line_id == self.id,
            InwardQC.is_deleted == False,
            InwardQC.status != "Draft",
        ).order_by(InwardQC.id.desc()).first()

    @property
    def passed_qty(self):
        # QC me jitna maal PASS hua (bill sirf isi par ban sakta hai). QC nahi hua to 0.
        qc = self.final_qc
        return qc.passed_qty if qc else 0

    @property
    def billed_qty(self):
        # Is lot par bane bill-lines ka jod. Cancelled / remove kiye hue bill ki quantity nahi ginte.
        total = 0
        for line in self.invoice_lines:
            if line.invoice.is_deleted or line.invoice.status == "Cancelled":
                continue
            total += line.qty
        return round(total, 4)

    @property
    def rejected_qty(self):
        qc = self.final_qc
        return qc.rejected_qty if qc else 0

    @property
    def billable_qty(self):
        # Client rule (2026-10-14): vendor ka bill final hota hai, to bill GRN me aayi POORI qty ka banta hai (rejected samet).
        # QC final hone ke baad hi, aur tab tak jab tak is GRN par koi chalta hua bill nahi hai.
        if self.final_qc is None or _grn_billing_invoice(self.grn) is not None:
            return 0
        return max(round(self.received_qty - self.billed_qty, 4), 0)        


class InwardQC(CreatedAtMixin, db.Model):
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

    # F11: QC report / certificate ki file (optional). DB me path hamesha "/" se: "inward_qc/<id>/<naam>" (UPLOAD_FOLDER ke andar)
    report_file = db.Column(db.String(255), nullable=True)

    # Draft / Passed / Partial / Failed
    status = db.Column(db.String(20), default="Draft", nullable=False)
    remarks = db.Column(db.String(255), nullable=True)

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

class Charge(CreatedAtMixin, db.Model):
    __tablename__ = 'charges'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_deleted = db.Column(db.Boolean, default=False)

class State(CreatedAtMixin, db.Model):
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


class VendorType(CreatedAtMixin, db.Model):
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


class ProductionOrder(CreatedAtMixin, db.Model):
    # Finished product banane ka order. Recipe yahan copy hoti hai, product master se live nahi judti.
    __tablename__ = "production_orders"

    id = db.Column(db.Integer, primary_key=True)
    prod_no = db.Column(db.String(20), unique=True, nullable=False)

    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    product = db.relationship("Product", foreign_keys=[product_id])

    # Kis production line me chal raha hai: Queue se Start karte waqt chuni jaati hai (lines bani hon tab zaroori)
    line_id = db.Column(db.Integer, db.ForeignKey("production_lines.id"), nullable=True)
    line = db.relationship("ProductionLine", foreign_keys=[line_id])
    # Line ki daily capacity se kam kaam laga ho to kitna KG khaali raha aur kyun (client change #1: reason mandatory)
    under_capacity_kg = db.Column(db.Float, nullable=True)
    under_capacity_reason = db.Column(db.String(255), nullable=True)

    order_date = db.Column(db.Date, nullable=False)
    planned_qty = db.Column(db.Float, nullable=False)
    # KG product pe 1. Doosri unit pe ek piece ka weight, taaki batch KG nikal sake.
    unit_weight = db.Column(db.Float, default=1, nullable=False)
    status = db.Column(db.String(20), default="Draft", nullable=False)
    remarks = db.Column(db.String(255), nullable=True)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

    # Plan (order banate waqt ka andaza; asli time baad me Routing tracker se milaya jayega)
    planned_start_date = db.Column(db.Date, nullable=True)
    planned_end_date = db.Column(db.Date, nullable=True)
    planned_hours = db.Column(db.Float, nullable=True)           # saare stages ke ghante ka jod
    planned_days = db.Column(db.Integer, nullable=True)          # kaam ke din (Sunday off)
    daily_capacity = db.Column(db.Float, nullable=True)          # roz ka maximum, KG (sabse dheeme stage se)
    bottleneck_stage = db.Column(db.String(100), nullable=True)  # kaunsa stage sabse dheema hai

    # Queue: open orders ek line me chalte hain (1 = sabse pehle). Status: Draft -> Released -> In production -> (Completed baad me) / Cancelled.
    queue_position = db.Column(db.Integer, nullable=True)
    needed_by_date = db.Column(db.Date, nullable=True)           # client ko kab tak chahiye (optional); der hone par list me "Late" dikhta hai
    earliest_start_date = db.Column(db.Date, nullable=True)      # isse pehle start nahi; asli start / end queue + machines + RM se nikalte hain
    # Production planning (client meeting 2, #6): order form me line / machine nahi chunte; pehle default machines se andaza plan banta hai (False),
    # production manager Planning page par line + machines chun kar pakka karta hai (True). Release tabhi jab True. Purane orders True.
    plan_confirmed = db.Column(db.Boolean, default=True, server_default="1", nullable=False)
    # Bundle (client meeting 2, #5): ek party ke order me kai products ho to har product ka apna normal PROD order banta hai
    # (recipe, stages, line sab alag), par sab ek hi bundle number (BND-2026-001) se jude rehte hain. Single order me khaali.
    bundle_no = db.Column(db.String(20), nullable=True, index=True)
    started_date = db.Column(db.Date, nullable=True)             # "Start production" dabane ka din

    # Cancel: order delete nahi hota, status "Cancelled" + wajah (audit trail ke liye)
    cancel_reason = db.Column(db.String(255), nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)

    # C18: "Make extra for scrap?" — Yes ho to metal (recipe lines) ordered qty se extra_percent % zyada issue hota hai taaki scrap ke baad bhi ordered qty bane.
    # 0 = No. Order ki planned_qty badalti nahi (customer ne jitna manga wahi); sirf material zyada lagta hai.
    extra_percent = db.Column(db.Float, default=0, server_default="0", nullable=False)
    # C18: order complete hone par good qty ordered se kam ho to user ka faisla: "Cover from stock" / "Balance order" / "Closed as is" (+ note).
    short_action = db.Column(db.String(20), nullable=True)
    short_note = db.Column(db.String(255), nullable=True)
    short_resolved_at = db.Column(db.DateTime, nullable=True)
    # Balance order: kami poori karne ke liye bana naya order, original order ki id yahan (card par "Balance of PROD-...").
    balance_for_id = db.Column(db.Integer, db.ForeignKey("production_orders.id"), nullable=True)
    balance_for = db.relationship("ProductionOrder", remote_side=[id], foreign_keys=[balance_for_id])

    @property
    def issue_status(self):
        # Material issue ka haal, quantity se nikala (status column me store nahi): Not issued / Partly issued / Fully issued
        if not self.lines:
            return "No materials"
        issued_any = False
        all_done = True
        for line in self.lines:
            if line.issued_qty > 0:
                issued_any = True
            if line.remaining_qty > 0:
                all_done = False
        if all_done:
            return "Fully issued"
        return "Partly issued" if issued_any else "Not issued"


class ProductionOrderLine(CreatedAtMixin, db.Model):
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
    # True = product ke Packing Material section se aayi line (spool / sleeve / box); qty order KG / kg_per_pack
    is_packing = db.Column(db.Boolean, default=False, nullable=False)
    # Recipe se copy: ye material kis stage me jaata hai (order par freeze; master badle to purana order na badle)
    work_stage_id = db.Column(db.Integer, db.ForeignKey("work_stage.id"), nullable=True)
    work_stage = db.relationship("WorkStage", foreign_keys=[work_stage_id])
    # Stage complete par likhi gayi asli RM use (ek hi baar, rounds nahi). None = abhi likhi nahi (purane orders me bhi None: output par
    # WIP ka saara maal use ginte hain, pehle jaisa).
    used_qty = db.Column(db.Float, nullable=True)
    # Extra material allowance (%): har RM ka apna % (order banate waqt). Itna extra issue ho sakta hai (kharab / bacha maal ke liye);
    # zaroori nahi: jo use na ho wo output se pehle store me wapas aata hai.
    allowance_percent = db.Column(db.Float, default=0, server_default="0", nullable=False)
    # Packing line ho to "har kg_per_pack KG par 1 pack" (product ki packing item se copy). Routing me KG se pack ginti isi se nikalti hai.
    kg_per_pack = db.Column(db.Float, nullable=True)

    @property
    def allowance_qty(self):
        return round((self.required_qty or 0) * (self.allowance_percent or 0) / 100, 4)

    @property
    def issued_qty(self):
        # Is line ke liye ab tak kitna RM production ko diya gaya: Draft + Posted issues ginte hain
        # (Cancelled / remove kiye hue nahi) — wahi tarika jo bill me "billed qty" ka hai
        total = 0
        for issue_line in self.issue_lines:
            issue = issue_line.issue
            if issue.is_deleted or issue.status == "Cancelled":
                continue
            total += issue_line.qty - issue_line.returned_qty        # Material return ka wapas aaya hissa ghata do
        return round(total, 4)

    @property
    def remaining_qty(self):
        # Zaroorat ka wo hissa jo abhi issue hona baaki hai (allowance alag). Stage ki RM use likh di gayi ho to aur kuch issue nahi hona.
        if self.used_qty is not None:
            return 0
        return max(round(self.required_qty - self.issued_qty, 4), 0)

    @property
    def allowance_remaining_qty(self):
        # Allowance ka wo hissa jo abhi issue ho sakta hai: (zaroorat + allowance) - ab tak issue, par zaroorat wale hisse ke baad ka
        if self.used_qty is not None:
            return 0
        total_left = round(self.required_qty + self.allowance_qty - self.issued_qty, 4)
        return max(round(total_left - self.remaining_qty, 4), 0)

    @property
    def open_demand_qty(self):
        # Material plan / alerts ke liye: abhi aur kitna maal chahiye hoga (zaroorat + allowance), stage ki use likh di ho to 0
        return round(self.remaining_qty + self.allowance_remaining_qty, 4)

    @property
    def leftover_qty(self):
        # Stage me use likhne ke baad jo issued maal production me bacha hai (output se pehle wapas karna hai); use likhi na ho to 0
        if self.used_qty is None:
            return 0
        return max(round(self.issued_qty - self.used_qty, 4), 0)


class PaymentTerm(CreatedAtMixin, db.Model):
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


class PartyDocument(CreatedAtMixin, db.Model):
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

class RejectionMemo(CreatedAtMixin, db.Model):
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

class RMQCParameter(CreatedAtMixin, db.Model):
    __tablename__ = "rm_qc_parameters"

    id = db.Column(db.Integer, primary_key=True)

    raw_material_id = db.Column(db.Integer, db.ForeignKey("raw_materials.id"), nullable=False)
    raw_material = db.relationship("RawMaterial", foreign_keys=[raw_material_id], backref="qc_parameters")

    name = db.Column(db.String(100), nullable=False)
    unit_label = db.Column(db.String(20), nullable=True)
    
    # "range" = number type hota hai, min/max se pass-fail; "pass_fail" = lab seedha Pass/Fail chune (visual jaisa)
    check_type = db.Column(db.String(20), default="range", nullable=False)
    # Dono optional: purity me sirf min, impurity me sirf max, gauge me dono
    min_value = db.Column(db.Float, nullable=True)
    max_value = db.Column(db.Float, nullable=True)

    # Chhota number pehle dikhega
    sort_order = db.Column(db.Integer, default=0, nullable=False)

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)



class InwardQCResult(CreatedAtMixin, db.Model):
    # Ek inspection (InwardQC) ke ek parameter ka result: "Purity 99.7 -> Pass".
    # Parameter ka naam / unit / limits yahan COPY (snapshot) hote hain. Baad me template badle
    # ya parameter remove ho jaye to bhi purana result waisa hi rahe (production order me recipe copy jaisa).
    __tablename__ = "inward_qc_results"

    id = db.Column(db.Integer, primary_key=True)

    inward_qc_id = db.Column(db.Integer, db.ForeignKey("inward_qc.id"), nullable=False)
    # backref: inspection.results = us inspection ke saare parameter results
    inward_qc = db.relationship("InwardQC", foreign_keys=[inward_qc_id], backref="results")

    # Sirf reference ke liye. Asli data neeche ki copy me hai (parameter badle/hate to bhi result safe)
    parameter_id = db.Column(db.Integer, db.ForeignKey("rm_qc_parameters.id"), nullable=True)

    # ---- Snapshot: result save karte waqt parameter ki copy ----
    parameter_name = db.Column(db.String(100), nullable=False)
    unit_label = db.Column(db.String(20), nullable=True)
    check_type = db.Column(db.String(20), nullable=False)
    min_value = db.Column(db.Float, nullable=True)
    max_value = db.Column(db.Float, nullable=True)

    # ---- Lab ka result ----
    # Range parameter me naapi hui value; pass/fail parameter me koi number nahi hota (isliye nullable)
    actual_value = db.Column(db.Float, nullable=True)
    # True = pass, False = fail. Server nikalta hai (range: limits se; pass/fail: lab ka chuna hua jawab)
    passed = db.Column(db.Boolean, nullable=False)

    @property
    def standard_text(self):
        # Parameter ki limit padhne layak text me: "Min 90" / "2 to 3.05" / "Max 0.1" / "Pass / Fail"
        if self.check_type == "pass_fail":
            return "Pass / Fail"
        if self.min_value is not None and self.max_value is not None:
            return f"{self.min_value:g} to {self.max_value:g}"
        if self.min_value is not None:
            return f"Min {self.min_value:g}"
        if self.max_value is not None:
            return f"Max {self.max_value:g}"
        return "—"

    @property
    def fail_text(self):
        # Memo ke reason ke liye: fail hue parameter ka ek line ka text
        if self.check_type == "pass_fail":
            return f"{self.parameter_name} failed"
        unit = f" {self.unit_label}" if self.unit_label else ""
        return f"{self.parameter_name} {self.actual_value:g}{unit} (standard: {self.standard_text}{unit})"

    @property
    def summary(self):
        # View panel (JS) ke liye ek dictionary: template me data-attribute me JSON ban kar jayegi
        return {
            "name": self.parameter_name,
            "unit": self.unit_label or "",
            "standard": self.standard_text,
            "actual": None if self.actual_value is None else f"{self.actual_value:g}",
            "passed": self.passed,
        }

class PurchaseInvoice(CreatedAtMixin, db.Model):
    __tablename__ = "purchase_invoices"

    id = db.Column(db.Integer, primary_key=True)
    # Hamara apna number (PI-2026-001): route banata hai. Vendor ke bill ka number alag column me hai.
    pi_no = db.Column(db.String(20), unique=True, nullable=False)

    vendor_id = db.Column(db.Integer, db.ForeignKey("vendors.id"), nullable=False)
    vendor = db.relationship("Vendor", foreign_keys=[vendor_id])

    # Vendor ke bill par jo number likha hai. Ek vendor ka same number do baar nahi (route check karega)
    vendor_invoice_no = db.Column(db.String(50), nullable=False)
    invoice_date = db.Column(db.Date, nullable=False)

    # "intra" = CGST + SGST (vendor ka state = hamare branch ka state), "inter" = IGST. Bill banate waqt ki copy
    tax_type = db.Column(db.String(10), nullable=False)

    # Draft -> Posted -> Cancelled. Draft aur Posted dono "billed" ginte hain (lot do baar bill na ho);
    # Cancelled bill ki quantity wapas khul jaati hai
    status = db.Column(db.String(20), default="Draft", nullable=False)
    remarks = db.Column(db.String(255), nullable=True)

    # Totals save / post par server nikaal ke yahan rakhta hai (rupee, 2 decimal tak round)
    subtotal = db.Column(db.Float, default=0, nullable=False)       # discount ke baad, tax se pehle
    tax_total = db.Column(db.Float, default=0, nullable=False)
    charges_total = db.Column(db.Float, default=0, nullable=False)  # freight / other charges: Add (+) aur Minus (-) ka jod
    total_amount = db.Column(db.Float, default=0, nullable=False)   # vendor ko dena baaki

    # Client rule: ek GRN = ek bill. Purane bills (lot-wise bane the) me ye khaali hai.
    grn_id = db.Column(db.Integer, db.ForeignKey("grns.id"), nullable=True)
    grn = db.relationship("GRN", foreign_keys=[grn_id], backref="bills")

    # F9: naye bill me GST items + charges ke total par (True). Purane bills me False (server_default): unka total nahi badla.
    gst_on_charges = db.Column(db.Boolean, default=True, server_default=db.false(), nullable=False)

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

    @property
    def po(self):
        # Bill kis PO ka hai (list me PO-wise grouping ke liye). Naye bill me GRN se; purane (lot-wise) bill me pehli line ke GRN se.
        if self.grn is not None:
            return self.grn.po
        for line in self.lines:
            grn_line = line.grn_line
            if grn_line is not None and grn_line.grn is not None:
                return grn_line.grn.po
        return None

    @property
    def lines_tax_total(self):
        # Sirf lines ka GST (charges ka GST nahi)
        total = 0
        for line in self.lines:
            total += line.tax_amount
        return round(total, 2)

    @property
    def charges_tax(self):
        # Charges par laga GST = bill ka poora GST - lines ka GST. Purane bills me 0.
        if not self.gst_on_charges:
            return 0
        return round(self.tax_total - self.lines_tax_total, 2)

    @property
    def rejected_note(self):
        # View panel ke liye: is bill me kitna maal QC me reject hua tha (bill me shamil hai, Return se handle hoga)
        rows = []
        for line in self.lines:
            grn_line = line.grn_line
            rejected = grn_line.rejected_qty if grn_line else 0
            if rejected > 0:
                rows.append({"material": line.raw_material.name if line.raw_material else "",
                             "qty": rejected, "unit": line.unit.code if line.unit else ""})
        return rows

    @property
    def active_returns(self):
        # Is bill ke wo returns jo abhi chal rahe hain (Cancelled / remove kiye hue nahi). backref: PurchaseReturn.invoice
        active = []
        for purchase_return in self.returns:
            if purchase_return.is_deleted or purchase_return.status == "Cancelled":
                continue
            active.append(purchase_return)
        return active

    @property
    def returned_amount(self):
        # Active returns ka total credit (vendor ne itna payable maaf kiya)
        total = 0
        for purchase_return in self.active_returns:
            total += purchase_return.total_amount
        return round(total, 2)

    @property
    def can_return(self):
        # Return sirf Posted bill par, aur tab jab kisi line ki kuch qty wapas bhejne ke liye bachi ho
        if self.status != "Posted":
            return False
        for line in self.lines:
            if line.returnable_qty > 0:
                return True
        return False

    @property
    def returns_summary(self):
        # View panel (JS) ke liye: is bill ke saare returns (Cancelled bhi, status ke saath), naye pehle
        rows = []
        for purchase_return in sorted(self.returns, key=lambda r: r.id, reverse=True):
            if purchase_return.is_deleted:
                continue
            rows.append({
                "pr_no": purchase_return.pr_no,
                "date": purchase_return.return_date.strftime("%d %b %Y") if purchase_return.return_date else "",
                "total": purchase_return.total_amount,
                "status": purchase_return.status,
            })
        return rows

class PurchaseInvoiceLine(CreatedAtMixin, db.Model):

    # Bill ki ek line = ek lot (GRN line) ka kitna hissa bill hua. Rate / tax yahan COPY (snapshot) rehte hain,
    # taaki baad me PO ya tax master badle to post ho chuka bill na badle.
    __tablename__ = "purchase_invoice_lines"

    id = db.Column(db.Integer, primary_key=True)

    invoice_id = db.Column(db.Integer, db.ForeignKey("purchase_invoices.id"), nullable=False)
    invoice = db.relationship("PurchaseInvoice", foreign_keys=[invoice_id], backref="lines")

    # Kaun sa lot. backref: grn_line.invoice_lines = is lot par bane saare bill-lines (billed qty isi se nikalegi)
    grn_line_id = db.Column(db.Integer, db.ForeignKey("grn_lines.id"), nullable=False)
    grn_line = db.relationship("GRNLine", foreign_keys=[grn_line_id], backref="invoice_lines")

    raw_material_id = db.Column(db.Integer, db.ForeignKey('raw_materials.id'), nullable=False)
    raw_material = db.relationship("RawMaterial", foreign_keys=[raw_material_id])

    unit_id = db.Column(db.Integer, db.ForeignKey("units.id"), nullable=False)
    unit = db.relationship("Unit", foreign_keys=[unit_id])

    qty = db.Column(db.Float, nullable=False)
    rate = db.Column(db.Float, nullable=False)
    discount_percent = db.Column(db.Float, default=0, nullable=False)

    tax_rate_id = db.Column(db.Integer, db.ForeignKey("tax_rates.id"), nullable=False)
    tax_rate = db.relationship("TaxRate", foreign_keys=[tax_rate_id])
    tax_percent = db.Column(db.Float, nullable=False)

    @property
    def taxable_amount(self):
        # Discount ke baad, tax se pehle: qty x rate, phir discount % kaat ke. Paise tak (2 decimal) round.
        return round(self.qty * self.rate * (1 - self.discount_percent / 100), 2)

    @property
    def tax_amount(self):
        # Is line ka GST: taxable amount ka tax_percent %
        return round(self.taxable_amount * self.tax_percent / 100, 2)

    @property
    def summary(self):
        # View panel (JS) ke liye ek dictionary: template me data-attribute me JSON ban kar jayegi
        gl = self.grn_line
        rm = self.raw_material
        return {
            "material": f"{rm.code} {rm.name}" if rm else "",
            "lot": gl.batch_lot_no if gl else "",
            "grn": gl.grn.grn_no if gl and gl.grn else "",
            "qty": f"{self.qty:g}",
            "unit": self.unit.code if self.unit else "",
            "rate": self.rate,
            "discount": self.discount_percent,
            "tax_percent": self.tax_percent,
            "taxable": self.taxable_amount,
            "tax": self.tax_amount,
        }

    @property
    def returned_qty(self):
        total = 0
        for return_line in self.return_lines:
            if return_line.purchase_return.is_deleted or return_line.purchase_return.status == "Cancelled":
                continue
            total += return_line.qty
        return round(total, 4)

    def returned_from(self, source):
        # Is bill line se "passed" ya "rejected" me se kitna wapas ja chuka (Cancelled / remove kiya hua return nahi ginte)
        total = 0
        for return_line in self.return_lines:
            if return_line.purchase_return.is_deleted or return_line.purchase_return.status == "Cancelled":
                continue
            if (return_line.source or "passed") == source:
                total += return_line.qty
        return round(total, 4)

    @property
    def rejected_cap(self):
        # Naye bill (GRN-wise) me QC me reject hua maal bhi bill me hai, to wo "Rejected" me se wapas ja sakta hai.
        # Purane bill me rejected maal bill hua hi nahi tha, isliye 0.
        if self.invoice is None or self.invoice.grn_id is None or self.grn_line is None:
            return 0
        return min(self.grn_line.rejected_qty or 0, self.qty)

    @property
    def passed_cap(self):
        return round(self.qty - self.rejected_cap, 4)

    @property
    def returnable_passed(self):
        return max(round(self.passed_cap - self.returned_from("passed"), 4), 0)

    @property
    def returnable_rejected(self):
        return max(round(self.rejected_cap - self.returned_from("rejected"), 4), 0)

    @property
    def returnable_qty(self):
        return round(self.returnable_passed + self.returnable_rejected, 4)

    @property
    def return_info(self):
        # Return panel (JS) ke liye: bill ki qty, kitna wapas ja chuka, kitna aur ja sakta hai,
        # aur paisa nikalne ke liye rate / discount / tax (panel me live value isi se dikhti hai)
        grn_line = self.grn_line
        material = self.raw_material
        return {
            "id": self.id,
            "material": f"{material.code} {material.name}" if material else "",
            "grn": grn_line.grn.grn_no if grn_line and grn_line.grn else "",
            "lot": grn_line.batch_lot_no if grn_line else "",
            "unit": self.unit.code if self.unit else "",
            "qty": self.qty,
            "returned": self.returned_qty,
            "returnable": self.returnable_qty,
            "returnable_passed": self.returnable_passed,
            "returnable_rejected": self.returnable_rejected,
            "rate": self.rate,
            "discount": self.discount_percent,
            "tax_percent": self.tax_percent,
        }

class PurchaseInvoiceCharge(CreatedAtMixin, db.Model):
    # Bill par extra charge (freight, packing, etc.): Charges Master se, PO ke charges jaisa.
    # "add" total badhata hai, "minus" total se ghatata hai.
    __tablename__ = "purchase_invoice_charges"

    id = db.Column(db.Integer, primary_key=True)

    invoice_id = db.Column(db.Integer, db.ForeignKey("purchase_invoices.id"), nullable=False)
    invoice = db.relationship("PurchaseInvoice", foreign_keys=[invoice_id], backref="charge_lines")

    charge_id = db.Column(db.Integer, db.ForeignKey("charges.id"), nullable=False)
    charge = db.relationship("Charge", foreign_keys=[charge_id])

    amount = db.Column(db.Float, nullable=False)
    effect = db.Column(db.String(10), nullable=False)   # "add" ya "minus"

    @property
    def signed_amount(self):
        # Total me asar: "add" ka +amount, "minus" ka -amount
        return -self.amount if self.effect == "minus" else self.amount

    @property
    def summary(self):
        # View panel (JS) ke liye dictionary
        return {"name": self.charge.name if self.charge else "Charge", "amount": self.amount, "effect": self.effect}

class PurchaseReturn(CreatedAtMixin, db.Model):
    # Posted bill ke against maal vendor ko wapas bhejna (debit note): vendor ka payable ghatata hai.
    # Bill jaisa hi header + lines pattern. Bill khud Posted hi rehta hai.
    __tablename__ = "purchase_returns"

    id = db.Column(db.Integer, primary_key=True)
    # Hamara number (PR-2026-001): route banata hai
    pr_no = db.Column(db.String(20), unique=True, nullable=False)

    # Kis bill ke against. backref: invoice.returns = is bill par bane saare returns
    invoice_id = db.Column(db.Integer, db.ForeignKey("purchase_invoices.id"), nullable=False)
    invoice = db.relationship("PurchaseInvoice", foreign_keys=[invoice_id], backref="returns")

    return_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.String(255), nullable=False)       # PRD: reason zaroori

    # Posted -> Cancelled (Draft nahi: return seedha post hota hai)
    status = db.Column(db.String(20), default="Posted", nullable=False)

    # Totals route nikaal ke rakhta hai (rupee, 2 decimal tak round)
    subtotal = db.Column(db.Float, default=0, nullable=False)     # discount ke baad, tax se pehle
    tax_total = db.Column(db.Float, default=0, nullable=False)
    charges_total = db.Column(db.Float, default=0, nullable=False)    # return charges: Add (+) aur Minus (-) ka jod
    total_amount = db.Column(db.Float, default=0, nullable=False)     # = subtotal + tax + charges; vendor ke payable se itna ghatega

    # F9: naye return me GST goods + charges ke total par (True). Purane returns me False (server_default): unka total nahi badla.
    gst_on_charges = db.Column(db.Boolean, default=True, server_default=db.false(), nullable=False)

    @property
    def lines_tax_total(self):
        total = 0
        for line in self.lines:
            total += line.tax_amount
        return round(total, 2)

    @property
    def charges_tax(self):
        # Charges par laga GST = return ka poora GST - goods lines ka GST. Purane returns me 0.
        if not self.gst_on_charges:
            return 0
        return round(self.tax_total - self.lines_tax_total, 2)

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)


class PurchaseReturnLine(CreatedAtMixin, db.Model):
    # Return ki ek line = bill ki ek line ka kitna hissa wapas gaya. Rate / tax yahan nahi:
    # bill ki line se hi nikalenge (wo kabhi badalti nahi)
    __tablename__ = "purchase_return_lines"

    id = db.Column(db.Integer, primary_key=True)

    return_id = db.Column(db.Integer, db.ForeignKey("purchase_returns.id"), nullable=False)
    # "return" Python ka keyword hai, isliye relationship ka naam purchase_return
    purchase_return = db.relationship("PurchaseReturn", foreign_keys=[return_id], backref="lines")

    # backref: invoice_line.return_lines = is bill line par bane saare return-lines (returned qty isi se nikalegi)
    invoice_line_id = db.Column(db.Integer, db.ForeignKey("purchase_invoice_lines.id"), nullable=False)
    invoice_line = db.relationship("PurchaseInvoiceLine", foreign_keys=[invoice_line_id], backref="return_lines")

    # F7: ye maal "passed" me se wapas gaya ya "rejected" me se (client: return banate waqt puchna). Purani rows = passed.
    source = db.Column(db.String(10), default="passed", server_default="passed", nullable=False)

    qty = db.Column(db.Float, nullable=False)   
    
    @property
    def taxable_amount(self):
        line = self.invoice_line
        return round(self.qty * line.rate *(1 - line.discount_percent/100), 2)

    @property
    def tax_amount(self):
        return round(self.taxable_amount * self.invoice_line.tax_percent/100, 2)

    @property
    def summary(self):
        # View panel (JS) ke liye ek dictionary: material, lot, qty, aur bill line wala rate / discount / tax
        line = self.invoice_line
        grn_line = line.grn_line
        material = line.raw_material
        return {
            "material": f"{material.code} {material.name}" if material else "",
            "grn": grn_line.grn.grn_no if grn_line and grn_line.grn else "",
            "lot": grn_line.batch_lot_no if grn_line else "",
            "source": self.source or "passed",
            "qty": f"{self.qty:g}",
            "unit": line.unit.code if line.unit else "",
            "rate": line.rate,
            "discount": line.discount_percent,
            "tax_percent": line.tax_percent,
            "taxable": self.taxable_amount,
            "tax": self.tax_amount,
        }

class PurchaseReturnCharge(CreatedAtMixin, db.Model):
    # Return par extra charge (freight, handling, restocking fee...): Charges Master se, bill / PO ke charges jaisa.
    # Return ke total par asar: "add" total badhata hai (vendor hamara kharcha lauta raha hai),
    # "minus" total ghatata hai (vendor apni fees kaat raha hai).
    __tablename__ = "purchase_return_charges"

    id = db.Column(db.Integer, primary_key=True)

    return_id = db.Column(db.Integer, db.ForeignKey("purchase_returns.id"), nullable=False)
    purchase_return = db.relationship("PurchaseReturn", foreign_keys=[return_id], backref="charge_lines")

    charge_id = db.Column(db.Integer, db.ForeignKey("charges.id"), nullable=False)
    charge = db.relationship("Charge", foreign_keys=[charge_id])

    amount = db.Column(db.Float, nullable=False)
    effect = db.Column(db.String(10), nullable=False)   # "add" ya "minus"

    @property
    def signed_amount(self):
        # Return ke total par asar: "add" ka +amount, "minus" ka -amount
        return -self.amount if self.effect == "minus" else self.amount

    @property
    def summary(self):
        # View panel (JS) ke liye dictionary
        return {"name": self.charge.name if self.charge else "Charge", "amount": self.amount, "effect": self.effect}


# ======================= Inventory (stock ledger) =======================
# Stock ledger = bank ki passbook: ek baar likhi row kabhi badalti / mitti nahi. Galti = ulti row. Balance kahin store nahi
# hota — rows ka SUM hai. Saare rules app/inventory/posting.py me.

class StockLot(CreatedAtMixin, db.Model):
    # Ek lot = ek GRN line. lot_code hamara apna (LOT-0001); vendor ka batch number sirf copy hai.
    __tablename__ = "stock_lots"

    id = db.Column(db.Integer, primary_key=True)
    lot_code = db.Column(db.String(20), unique=True, nullable=False)

    # GRN wale lot ki GRN line. Opening stock (software shuru hone se pehle ka maal) ka koi GRN nahi hota, isliye khaali.
    grn_line_id = db.Column(db.Integer, db.ForeignKey("grn_lines.id"), unique=True, nullable=True)
    grn_line = db.relationship("GRNLine", foreign_keys=[grn_line_id], backref=db.backref("stock_lot", uselist=False))

    # "GRN" ya "OPENING". Opening lot me unit yahin likhi hoti hai (GRN lot me PO line ki unit se aati hai)
    source = db.Column(db.String(10), default="GRN", server_default="GRN", nullable=False)
    unit_id = db.Column(db.Integer, db.ForeignKey("units.id"), nullable=True)
    unit = db.relationship("Unit", foreign_keys=[unit_id])

    raw_material_id = db.Column(db.Integer, db.ForeignKey("raw_materials.id"), nullable=False)
    raw_material = db.relationship("RawMaterial", foreign_keys=[raw_material_id])

    vendor_batch_no = db.Column(db.String(30), nullable=True)

    @property
    def rack(self):
        # Rack GRN line par chuna jaata hai (opening stock lot ka koi rack nahi => None)
        return self.grn_line.rack if self.grn_line else None

    @property
    def unit_code(self):
        # Is lot ki unit ka code: opening lot me apni, GRN lot me PO line se
        if self.unit is not None:
            return self.unit.code
        po_line = self.grn_line.po_line if self.grn_line else None
        return po_line.unit.code if po_line and po_line.unit else ""


class StockMovement(CreatedAtMixin, db.Model):
    # Stock ki ek entry: qty aur value dono signed (+ aaya, - gaya). Kabhi UPDATE / DELETE nahi (neeche listener rokta hai).
    __tablename__ = "stock_movements"

    id = db.Column(db.Integer, primary_key=True)
    movement_date = db.Column(db.Date, nullable=False)          # document ki business date (GRN date, QC date, return date)

    raw_material_id = db.Column(db.Integer, db.ForeignKey("raw_materials.id"), nullable=False)
    raw_material = db.relationship("RawMaterial", foreign_keys=[raw_material_id])
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False)
    warehouse = db.relationship("Warehouse", foreign_keys=[warehouse_id])
    lot_id = db.Column(db.Integer, db.ForeignKey("stock_lots.id"), nullable=False)
    lot = db.relationship("StockLot", foreign_keys=[lot_id], backref="movements")

    # GRN_RECEIPT, QC_OUT, QC_IN, PURCHASE_RETURN (reversal me wahi type, ulta sign)
    movement_type = db.Column(db.String(30), nullable=False)
    qty = db.Column(db.Float, nullable=False)                   # signed, 4 decimal
    value = db.Column(db.Float, nullable=False)                 # signed, 2 decimal (abhi PO rate par "estimated")

    ref_type = db.Column(db.String(20), nullable=False)         # GRN / QC / RETURN
    ref_id = db.Column(db.Integer, nullable=False)
    ref_no = db.Column(db.String(30), nullable=True)
    line_key = db.Column(db.String(30), nullable=False)         # document ki kaun si line (GRN line id / return line id)

    reverses_movement_id = db.Column(db.Integer, db.ForeignKey("stock_movements.id"), nullable=True, unique=True)
    note = db.Column(db.String(255), nullable=True)

    __table_args__ = (
        # Ek document line ka ek movement type do baar nahi (double click / dobara chalane se double entry nahi). Reversal rows chhoot.
        db.Index("uq_stock_movement_once", "ref_type", "ref_id", "line_key", "movement_type", unique=True,
                 sqlite_where=text("reverses_movement_id IS NULL")),
    )


@event.listens_for(StockMovement, "before_update")
def _stock_movement_no_update(mapper, connection, target):
    raise RuntimeError("Stock ledger rows are never edited. Add a reversing row instead.")


@event.listens_for(StockMovement, "before_delete")
def _stock_movement_no_delete(mapper, connection, target):
    raise RuntimeError("Stock ledger rows are never deleted. Add a reversing row instead.")



# ======================= Material issue (RM store se production / WIP ko) =======================
class MaterialIssue(CreatedAtMixin, db.Model):
    # Released production order ke liye RM store se WIP me dena. Draft -> Posted (stock tab badalta hai) -> Cancelled.
    __tablename__ = "material_issues"

    id = db.Column(db.Integer, primary_key=True)
    issue_no = db.Column(db.String(20), unique=True, nullable=False)

    production_order_id = db.Column(db.Integer, db.ForeignKey("production_orders.id"), nullable=False)
    production_order = db.relationship("ProductionOrder", foreign_keys=[production_order_id], backref="issues")

    issue_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default="Draft", nullable=False)
    remarks = db.Column(db.String(255), nullable=True)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    issued_by = db.Column(db.String(60), nullable=True)      # store se kisne diya (slip par)
    received_by = db.Column(db.String(60), nullable=True)    # production me kisne liya


class MaterialIssueLine(CreatedAtMixin, db.Model):
    # Ek line = ek RM lot ka kitna hissa diya gaya (traceability: kaun sa lot kis production order me gaya)
    __tablename__ = "material_issue_lines"

    id = db.Column(db.Integer, primary_key=True)
    issue_id = db.Column(db.Integer, db.ForeignKey("material_issues.id"), nullable=False)
    issue = db.relationship("MaterialIssue", foreign_keys=[issue_id], backref="lines")

    # Production order ki kaun si requirement line ke liye (issued qty isi se ginti hai)
    production_order_line_id = db.Column(db.Integer, db.ForeignKey("production_order_lines.id"), nullable=False)
    production_order_line = db.relationship("ProductionOrderLine", foreign_keys=[production_order_line_id], backref="issue_lines")

    raw_material_id = db.Column(db.Integer, db.ForeignKey("raw_materials.id"), nullable=False)
    raw_material = db.relationship("RawMaterial", foreign_keys=[raw_material_id])

    lot_id = db.Column(db.Integer, db.ForeignKey("stock_lots.id"), nullable=False)
    lot = db.relationship("StockLot", foreign_keys=[lot_id])

    qty = db.Column(db.Float, nullable=False)

    @property
    def returned_qty(self):
        # Is lot line ka jitna maal production se store me wapas aa chuka (sirf Posted returns)
        total = 0
        for return_line in self.return_lines:
            ret = return_line.material_return
            if ret.is_deleted or ret.status != "Posted":
                continue
            total += return_line.qty
        return round(total, 4)

    @property
    def returnable_qty(self):
        # Abhi bhi WIP me jo wapas ho sakta hai (issue Posted ho tabhi)
        if self.issue.is_deleted or self.issue.status != "Posted":
            return 0
        return max(round(self.qty - self.returned_qty, 4), 0)

    @property
    def summary(self):
        # View panel (JS) ke liye
        material = self.raw_material
        return {"material": (material.code + " " + material.name) if material else "",
                "lot": self.lot.lot_code if self.lot else "",
                "batch": self.lot.vendor_batch_no if self.lot else "",
                "qty": self.qty,
                "unit": material.base_unit.code if material and material.base_unit else ""}



class MaterialReturn(CreatedAtMixin, db.Model):
    # Production (WIP) se bacha / galat material store me wapas. Ek return = ek production order, lot-wise lines.
    # Posted (stock turant badalta hai) -> Cancelled (ulti rows, sirf tab jab maal store me abhi maujood ho).
    __tablename__ = "material_returns"

    id = db.Column(db.Integer, primary_key=True)
    return_no = db.Column(db.String(20), unique=True, nullable=False)

    production_order_id = db.Column(db.Integer, db.ForeignKey("production_orders.id"), nullable=False)
    production_order = db.relationship("ProductionOrder", foreign_keys=[production_order_id], backref="returns")

    return_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.String(60), nullable=False)
    status = db.Column(db.String(20), default="Posted", nullable=False)
    remarks = db.Column(db.String(255), nullable=True)
    returned_by = db.Column(db.String(60), nullable=True)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)


class MaterialWriteOff(CreatedAtMixin, db.Model):
    # Production ko diya hua maal jo na use hua na wapas mila (jaise 80 khali spool kho gaye): "missing" likha jaata hai (client meeting 2, #14).
    # Qty line ki used_qty me jud jaati hai, isliye output par ye WIP se consume hoti hai (cost FG me jaati hai) aur Consumption variance me dikhti hai.
    # Yahan sirf record: kisne likha, kyun, kitna (mismatch list ke liye).
    __tablename__ = "material_write_offs"

    id = db.Column(db.Integer, primary_key=True)
    production_order_id = db.Column(db.Integer, db.ForeignKey("production_orders.id"), nullable=False)
    production_order = db.relationship("ProductionOrder", foreign_keys=[production_order_id], backref="write_offs")
    order_line_id = db.Column(db.Integer, db.ForeignKey("production_order_lines.id"), nullable=False)
    order_line = db.relationship("ProductionOrderLine", foreign_keys=[order_line_id], backref="write_offs")
    raw_material_id = db.Column(db.Integer, db.ForeignKey("raw_materials.id"), nullable=False)
    raw_material = db.relationship("RawMaterial", foreign_keys=[raw_material_id])
    qty = db.Column(db.Float, nullable=False)
    reason = db.Column(db.String(255), nullable=False)
    written_off_by = db.Column(db.String(60), nullable=False)
    write_off_date = db.Column(db.Date, nullable=False)


class MaterialReturnLine(CreatedAtMixin, db.Model):
    # Kis issue line (yaani kis lot) ka kitna hissa wapas aaya
    __tablename__ = "material_return_lines"

    id = db.Column(db.Integer, primary_key=True)
    return_id = db.Column(db.Integer, db.ForeignKey("material_returns.id"), nullable=False)
    material_return = db.relationship("MaterialReturn", foreign_keys=[return_id], backref="lines")

    issue_line_id = db.Column(db.Integer, db.ForeignKey("material_issue_lines.id"), nullable=False)
    issue_line = db.relationship("MaterialIssueLine", foreign_keys=[issue_line_id], backref="return_lines")

    raw_material_id = db.Column(db.Integer, db.ForeignKey("raw_materials.id"), nullable=False)
    raw_material = db.relationship("RawMaterial", foreign_keys=[raw_material_id])
    lot_id = db.Column(db.Integer, db.ForeignKey("stock_lots.id"), nullable=False)
    lot = db.relationship("StockLot", foreign_keys=[lot_id])
    qty = db.Column(db.Float, nullable=False)

    @property
    def summary(self):
        material = self.raw_material
        return {"material": (material.code + " " + material.name) if material else "",
                "lot": self.lot.lot_code if self.lot else "", "batch": self.lot.vendor_batch_no if self.lot else "",
                "qty": self.qty, "unit": material.base_unit.code if material and material.base_unit else ""}


# ======================= Stock transfer (warehouse se warehouse) =======================
class StockTransfer(CreatedAtMixin, db.Model):
    # Draft -> In transit (Dispatch: maal source se nikla) -> Received (destination me aaya). Cancel sirf Draft / In transit par.
    __tablename__ = "stock_transfers"

    id = db.Column(db.Integer, primary_key=True)
    transfer_no = db.Column(db.String(20), unique=True, nullable=False)
    transfer_date = db.Column(db.Date, nullable=False)

    from_warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False)
    from_warehouse = db.relationship("Warehouse", foreign_keys=[from_warehouse_id])
    to_warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False)
    to_warehouse = db.relationship("Warehouse", foreign_keys=[to_warehouse_id])

    status = db.Column(db.String(20), default="Draft", nullable=False)
    vehicle_no = db.Column(db.String(30), nullable=True)
    eway_bill_no = db.Column(db.String(30), nullable=True)      # alag GSTIN ki branch ke beech zaroori
    remarks = db.Column(db.String(255), nullable=True)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

    @property
    def needs_eway(self):
        # Dono branch ke GSTIN alag hon to E-Way Bill chahiye (spec 6.2). Same branch / same GSTIN = nahi.
        a = self.from_warehouse.branch if self.from_warehouse else None
        b = self.to_warehouse.branch if self.to_warehouse else None
        if a is None or b is None or a.id == b.id:
            return False
        return (a.gstin or "") != (b.gstin or "")


class StockTransferLine(CreatedAtMixin, db.Model):
    __tablename__ = "stock_transfer_lines"

    id = db.Column(db.Integer, primary_key=True)
    transfer_id = db.Column(db.Integer, db.ForeignKey("stock_transfers.id"), nullable=False)
    transfer = db.relationship("StockTransfer", foreign_keys=[transfer_id], backref="lines")

    lot_id = db.Column(db.Integer, db.ForeignKey("stock_lots.id"), nullable=False)
    lot = db.relationship("StockLot", foreign_keys=[lot_id])
    qty = db.Column(db.Float, nullable=False)
    # Dispatch ke waqt lot ki value (transit me bhi value dikhe, aur Receive par wahi value destination me jaye)
    value = db.Column(db.Float, nullable=True)

    @property
    def summary(self):
        lot = self.lot
        material = lot.raw_material if lot else None
        unit = lot.unit_code if lot else ""
        return {"material": material.name if material else "", "lot": lot.lot_code if lot else "",
                "batch": lot.vendor_batch_no if lot else "", "qty": self.qty, "unit": unit}


# ======================= Stock adjustment (gina hua vs system; found / damaged) =======================
class AdjustmentReason(CreatedAtMixin, db.Model):
    # Adjustment ki wajah ki list (code me fixed nahi, database se)
    __tablename__ = "adjustment_reasons"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)


class StockAdjustment(CreatedAtMixin, db.Model):
    # Draft -> Pending approval -> Posted (approve karte hi stock badalta hai) ; Cancel sirf Draft / Pending par.
    __tablename__ = "stock_adjustments"

    id = db.Column(db.Integer, primary_key=True)
    adj_no = db.Column(db.String(20), unique=True, nullable=False)
    adj_date = db.Column(db.Date, nullable=False)
    adj_type = db.Column(db.String(20), nullable=False)          # increase / decrease / audit

    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False)
    warehouse = db.relationship("Warehouse", foreign_keys=[warehouse_id])
    reason_id = db.Column(db.Integer, db.ForeignKey("adjustment_reasons.id"), nullable=False)
    reason = db.relationship("AdjustmentReason", foreign_keys=[reason_id])

    status = db.Column(db.String(20), default="Draft", nullable=False)
    remarks = db.Column(db.String(255), nullable=True)
    approval_note = db.Column(db.String(255), nullable=True)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

    @property
    def net_qty(self):
        # Post ke baad asli farak; pehle sirf likhi hui qty (increase +, decrease -, audit me abhi pata nahi)
        total = 0
        for line in self.lines:
            total += line.delta if line.delta is not None else 0
        return round(total, 4)


class StockAdjustmentLine(CreatedAtMixin, db.Model):
    __tablename__ = "stock_adjustment_lines"

    id = db.Column(db.Integer, primary_key=True)
    adjustment_id = db.Column(db.Integer, db.ForeignKey("stock_adjustments.id"), nullable=False)
    adjustment = db.relationship("StockAdjustment", foreign_keys=[adjustment_id], backref="lines")

    lot_id = db.Column(db.Integer, db.ForeignKey("stock_lots.id"), nullable=False)
    lot = db.relationship("StockLot", foreign_keys=[lot_id])

    # increase / decrease me: kitna jodna / ghatana (positive). audit me: gina hua qty (counted).
    entered_qty = db.Column(db.Float, nullable=False)
    # Post ke waqt nikalta hai: +jod / -ghata. Audit me counted - book.
    delta = db.Column(db.Float, nullable=True)
    book_qty = db.Column(db.Float, nullable=True)                # post ke waqt system me kitna tha

    @property
    def summary(self):
        lot = self.lot
        material = lot.raw_material if lot else None
        unit = lot.unit_code if lot else ""
        return {"material": material.name if material else "", "lot": lot.lot_code if lot else "",
                "entered": self.entered_qty, "book": self.book_qty, "delta": self.delta, "unit": unit}



# ======================= Opening stock (software shuru hone se pehle ka maal) =======================
class OpeningStock(CreatedAtMixin, db.Model):
    # Ek warehouse ka shuruaati stock: Draft -> Posted (stock ledger me OPENING rows) -> Cancelled (sirf jab maal chheda na gaya ho)
    __tablename__ = "opening_stocks"

    id = db.Column(db.Integer, primary_key=True)
    opening_no = db.Column(db.String(20), unique=True, nullable=False)
    as_of_date = db.Column(db.Date, nullable=False)              # kis tareekh ka stock

    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False)
    warehouse = db.relationship("Warehouse", foreign_keys=[warehouse_id])

    status = db.Column(db.String(20), default="Draft", nullable=False)
    remarks = db.Column(db.String(255), nullable=True)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)


class OpeningStockLine(CreatedAtMixin, db.Model):
    __tablename__ = "opening_stock_lines"

    id = db.Column(db.Integer, primary_key=True)
    opening_id = db.Column(db.Integer, db.ForeignKey("opening_stocks.id"), nullable=False)
    opening = db.relationship("OpeningStock", foreign_keys=[opening_id], backref="lines")

    raw_material_id = db.Column(db.Integer, db.ForeignKey("raw_materials.id"), nullable=False)
    raw_material = db.relationship("RawMaterial", foreign_keys=[raw_material_id])
    qty = db.Column(db.Float, nullable=False)
    unit_cost = db.Column(db.Float, nullable=False)               # per unit bhaav (value = qty x unit_cost)
    batch_no = db.Column(db.String(30), nullable=True)
    # Post hone par banaya gaya lot
    lot_id = db.Column(db.Integer, db.ForeignKey("stock_lots.id"), nullable=True)
    lot = db.relationship("StockLot", foreign_keys=[lot_id])

    @property
    def summary(self):
        material = self.raw_material
        return {"material": (material.code + " " + material.name) if material else "", "qty": self.qty,
                "unit": material.base_unit.code if material and material.base_unit else "",
                "cost": self.unit_cost, "batch": self.batch_no or "", "lot": self.lot.lot_code if self.lot else ""}



class ProductRoutingStage(CreatedAtMixin, db.Model):
    # Product ka default routing: ye product kaun-kaun se work stages se guzarta hai (jaise Soldering wire: Flux prep -> Melting -> ... -> Packing).
    # Stage ka order Work Stage master ke sort_order se tay hota hai. Production Order ye list copy kar leta hai (recipe ki tarah).
    __tablename__ = "product_routing_stages"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    product = db.relationship("Product", foreign_keys=[product_id], backref="routing_stages")
    work_stage_id = db.Column(db.Integer, db.ForeignKey("work_stage.id"), nullable=False)
    work_stage = db.relationship("WorkStage", foreign_keys=[work_stage_id])

    __table_args__ = (db.UniqueConstraint("product_id", "work_stage_id", name="uq_product_routing_stage"),)



class MeltGroup(CreatedAtMixin, db.Model):
    # C9 phase 2: ek melt (furnace ki ek chal) = ek heat number. Same alloy ke kai orders ke Melting stages ek group me jud sakte hain (members),
    # wo saath start hote hain, saath hold / resume hote hain, aur ek hi lab test / TC unsabhi par lagta hai. Har melt (akele order ka bhi) ko heat no milta hai.
    __tablename__ = "melt_groups"

    id = db.Column(db.Integer, primary_key=True)
    heat_no = db.Column(db.String(20), unique=True, nullable=False)          # HT-2026-001
    work_stage_id = db.Column(db.Integer, db.ForeignKey("work_stage.id"), nullable=False)
    work_stage = db.relationship("WorkStage", foreign_keys=[work_stage_id])


class ProductionOrderStage(CreatedAtMixin, db.Model):
    # Order ka routing: us din ke stages ki copy (product ka routing badle to purana order nahi badlega) + unka planned time
    __tablename__ = "production_order_stages"

    id = db.Column(db.Integer, primary_key=True)
    production_order_id = db.Column(db.Integer, db.ForeignKey("production_orders.id"), nullable=False)
    production_order = db.relationship("ProductionOrder", foreign_keys=[production_order_id],
                                       backref=db.backref("stages", order_by="ProductionOrderStage.sort_order"))
    work_stage_id = db.Column(db.Integer, db.ForeignKey("work_stage.id"), nullable=False)
    work_stage = db.relationship("WorkStage", foreign_keys=[work_stage_id])
    stage_name = db.Column(db.String(100), nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    # C9 phase 2: Melting stage kis melt (heat number) ka hissa hai. Khaali = abhi koi melt nahi (Start par apne aap banta hai)
    melt_group_id = db.Column(db.Integer, db.ForeignKey("melt_groups.id"), nullable=True)
    melt_group = db.relationship("MeltGroup", foreign_keys=[melt_group_id], backref=db.backref("stages", order_by="ProductionOrderStage.id"))

    capacity_per_hour = db.Column(db.Float, nullable=True)       # chune hue machines ka jod, KG / hr
    daily_capacity = db.Column(db.Float, nullable=True)          # KG / din
    planned_hours = db.Column(db.Float, nullable=True)
    planned_days = db.Column(db.Float, nullable=True)
    # Is stage ka din-wise window (Sunday chhod ke). Machine clash isi se pakda jaata hai.
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)

    # Routing tracker: asli kaam ka record (Pending -> In progress -> Done). Stage kabhi delete nahi hota; history yahin rehti hai.
    status = db.Column(db.String(12), default="Pending", server_default="Pending", nullable=False)
    started_at = db.Column(db.DateTime, nullable=True)       # IST (naive)
    completed_at = db.Column(db.DateTime, nullable=True)
    operator = db.Column(db.String(60), nullable=True)
    qty_in = db.Column(db.Float, nullable=True)              # KG jo is stage me aaya (pichhle stage ka out; pehle stage me batch KG)
    qty_out = db.Column(db.Float, nullable=True)             # KG jo ye stage poora karke aage gaya
    scrap_qty = db.Column(db.Float, nullable=True)           # KG jo is stage me kharab hua
    # Scrap kis tarah ka aur kaisa: "Saleable" = Scrap warehouse me jaayega (output par), "Process loss" = chhota nuksaan, stock nahi banta
    scrap_type_id = db.Column(db.Integer, db.ForeignKey("scrap_types.id"), nullable=True)
    scrap_type = db.relationship("ScrapType", foreign_keys=[scrap_type_id])
    scrap_kind = db.Column(db.String(12), default="Saleable", server_default="Saleable", nullable=False)
    notes = db.Column(db.String(255), nullable=True)
    # Operator ne complete par asli kaam ke ghante likhe ho (stage do baar chala, beech me ruka) to wahi; warna start se end tak
    work_hours = db.Column(db.Float, nullable=True)
    # Billet (lattha) wale stage me: kitne lattha bane, ek lattha kitne KG ka (us waqt ka), aur scrap ka proof photo (uploads ke andar ka path)
    billet_count = db.Column(db.Integer, nullable=True)
    billet_weight = db.Column(db.Float, nullable=True)
    scrap_photo = db.Column(db.String(255), nullable=True)
    # Hold (lights gayi / machine kharab / QC): status "On hold" me timer ruk jaata hai. hold_minutes = ab tak ruke hue kul minute (pichhle holds ke),
    # held_at = abhi wala hold kab laga (None = hold nahi), hold_reason = abhi wali wajah.
    held_at = db.Column(db.DateTime, nullable=True)
    hold_reason = db.Column(db.String(120), nullable=True)
    hold_minutes = db.Column(db.Float, default=0, server_default="0", nullable=False)

    def worked_seconds(self, now):
        # Machine ne asal me kitni der kaam kiya: start se (ab ya finish tak) minus jitni der hold raha. Hold chal raha ho to timer wahi ruka hua dikhta hai.
        if not self.started_at:
            return 0
        end = self.completed_at or (self.held_at if self.held_at else now)
        return max(int((end - self.started_at).total_seconds() - (self.hold_minutes or 0) * 60), 0)

    @property
    def actual_hours(self):
        # Asli lage ghante (start se end tak, hold ka time hata kar). Abhi chal raha ho to start se ab tak nahi — sirf poora hone par
        if self.work_hours is not None and self.completed_at:
            return round(self.work_hours, 2)
        if self.started_at and self.completed_at:
            return round(self.worked_seconds(self.completed_at) / 3600, 2)
        return None


class ProductionOrderStageMachine(CreatedAtMixin, db.Model):
    # Is stage ke liye chuni hui machine (naam aur capacity ki copy, machine master badle to plan na badle)
    __tablename__ = "production_order_stage_machines"

    id = db.Column(db.Integer, primary_key=True)
    stage_id = db.Column(db.Integer, db.ForeignKey("production_order_stages.id"), nullable=False)
    stage = db.relationship("ProductionOrderStage", foreign_keys=[stage_id], backref="machines")
    machine_id = db.Column(db.Integer, db.ForeignKey("machines.id"), nullable=False)
    machine = db.relationship("Machines", foreign_keys=[machine_id])
    machine_name = db.Column(db.String(100), nullable=False)
    capacity_per_hour = db.Column(db.Float, nullable=False)
    hours_per_day = db.Column(db.Float, nullable=False)
    # Routing tracker: plan me thi (True) ya stage chalate waqt kisi doosri machine ko jod diya (False); aur asli me use hui ya nahi
    is_planned = db.Column(db.Boolean, default=True, server_default="1", nullable=False)
    used = db.Column(db.Boolean, default=False, server_default="0", nullable=False)



# ======================= Production output + Finished goods (FG) =======================
class ProductionOutput(CreatedAtMixin, db.Model):
    # Order ke saare stages poore hone par ek baar likhta hai: kitna Good / Rework / Scrap nikla. Post par: RM WIP se "use" ho jaata hai,
    # Good maal FG warehouse me aur Scrap, Scrap warehouse me aata hai, aur order "Completed" ho jaata hai. Posted -> Cancelled (ulti rows).
    __tablename__ = "production_outputs"

    id = db.Column(db.Integer, primary_key=True)
    output_no = db.Column(db.String(20), unique=True, nullable=False)           # OUT-2026-001
    batch_no = db.Column(db.String(30), unique=True, nullable=False)            # BATCH-WS-20261022-001 (FG ka batch)

    production_order_id = db.Column(db.Integer, db.ForeignKey("production_orders.id"), nullable=False)
    production_order = db.relationship("ProductionOrder", foreign_keys=[production_order_id], backref="outputs")

    output_date = db.Column(db.Date, nullable=False)
    good_qty = db.Column(db.Float, nullable=False)                               # order ki unit me (KG / roll ...)
    rework_qty = db.Column(db.Float, default=0, nullable=False)                  # abhi sirf record (dobara kaam ke liye); stock nahi banta
    scrap_qty = db.Column(db.Float, default=0, nullable=False)                   # saleable scrap (Scrap warehouse me jaata hai)
    loss_qty = db.Column(db.Float, default=0, server_default="0", nullable=False)  # process loss: sirf record, stock nahi
    total_value = db.Column(db.Float, default=0, nullable=False)                 # WIP se use hue RM ki kul value (Rs)
    unit_cost = db.Column(db.Float, default=0, nullable=False)                   # total_value / good_qty
    recorded_by = db.Column(db.String(60), nullable=True)
    remarks = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(12), default="Posted", nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    # Consumption variance ka review (kisne dekha, kab, kya note)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewed_by = db.Column(db.String(60), nullable=True)
    review_note = db.Column(db.String(255), nullable=True)
    # Fixed cost (client meeting 2, #1): mahine ka fixed kharcha per KG, output record hote waqt is batch par freeze ho jaata hai.
    # basis: NULL = fixed cost set nahi tha (sirf material cost), "Approx" = estimate, "Final" = mahina finalize hone ke baad ka asli rate.
    # Stock valuation (FGBatch / FGMovement unit_cost) sirf material cost par rehti hai; product cost = material + fixed Costing page me dikhti hai.
    fixed_cost_per_kg = db.Column(db.Float, default=0, server_default="0", nullable=False)
    fixed_cost_total = db.Column(db.Float, default=0, server_default="0", nullable=False)
    fixed_cost_basis = db.Column(db.String(8), nullable=True)


class FixedCostPeriod(CreatedAtMixin, db.Model):
    # Mahine ka estimated fixed kharcha (salary, kiraya, light...) jo effective_from tareekh se lagu hota hai. Badalna ho to NAYI row jodte hain;
    # purani rows aur purane batch ki cost kabhi nahi badalti (client: "jis tareekh se badla wahin se nayi costing").
    __tablename__ = "fixed_cost_periods"

    id = db.Column(db.Integer, primary_key=True)
    effective_from = db.Column(db.Date, nullable=False)
    monthly_amount = db.Column(db.Float, nullable=False)
    working_days = db.Column(db.Integer, nullable=False)          # din ka kharcha = monthly_amount / working_days
    note = db.Column(db.String(255), nullable=True)


class MachineExtraHours(CreatedAtMixin, db.Model):
    # C10: kisi ek din machine ke extra ghante (raat ki shift). Machine ka normal hours_per_day nahi badalta; scheduler sirf us tareekh ko lamba maanta hai.
    # Row delete nahi hoti: extra_hours 0 kar do to wo din wapas normal ho jaata hai.
    __tablename__ = "machine_extra_hours"
    __table_args__ = (db.UniqueConstraint("machine_id", "work_date", name="uq_machine_extra_hours_day"),)

    id = db.Column(db.Integer, primary_key=True)
    machine_id = db.Column(db.Integer, db.ForeignKey("machines.id"), nullable=False)
    machine = db.relationship("Machines")
    work_date = db.Column(db.Date, nullable=False)
    extra_hours = db.Column(db.Float, nullable=False, default=0)
    reason = db.Column(db.String(120), nullable=True)
    set_by = db.Column(db.String(60), nullable=True)


class FixedCostMonth(CreatedAtMixin, db.Model):
    # Mahina finalize: asli (final) fixed kharcha, us mahine ke total good KG se bhaga = final per KG. Ek mahina ek baar hi finalize hota hai.
    __tablename__ = "fixed_cost_months"

    id = db.Column(db.Integer, primary_key=True)
    month_start = db.Column(db.Date, unique=True, nullable=False)  # mahine ki pehli tareekh
    final_amount = db.Column(db.Float, nullable=False)
    total_kg = db.Column(db.Float, nullable=False)
    final_per_kg = db.Column(db.Float, nullable=False)
    finalized_at = db.Column(db.DateTime, default=utc_now, nullable=True)


class FGBatch(CreatedAtMixin, db.Model):
    # Ek batch = ek output ka Good maal (kind "FG") ya Scrap (kind "SCRAP"). Qty ka balance FGMovement ke SUM se, yahan store nahi.
    __tablename__ = "fg_batches"

    id = db.Column(db.Integer, primary_key=True)
    batch_no = db.Column(db.String(34), unique=True, nullable=False)
    kind = db.Column(db.String(8), default="FG", nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    product = db.relationship("Product", foreign_keys=[product_id])
    production_order_id = db.Column(db.Integer, db.ForeignKey("production_orders.id"), nullable=False)
    production_order = db.relationship("ProductionOrder", foreign_keys=[production_order_id])
    output_id = db.Column(db.Integer, db.ForeignKey("production_outputs.id"), nullable=False)
    output = db.relationship("ProductionOutput", foreign_keys=[output_id], backref="batches")
    mfg_date = db.Column(db.Date, nullable=False)
    unit_cost = db.Column(db.Float, default=0, nullable=False)

    # Rack (client change #10): FG warehouse ke andar batch kis rack me rakha hai. Optional; Scrap batch aur purane batch me khaali.
    rack_id = db.Column(db.Integer, db.ForeignKey("racks.id"), nullable=True)
    rack = db.relationship("Rack", foreign_keys=[rack_id])

    @property
    def balance(self):
        row = db.session.query(db.func.coalesce(db.func.sum(FGMovement.qty), 0), db.func.coalesce(db.func.sum(FGMovement.value), 0)).filter(
            FGMovement.batch_id == self.id).one()
        return round(row[0], 4), round(row[1], 2)

    @property
    def unit_code(self):
        return self.product.base_unit.code if self.product and self.product.base_unit else ""


class FGMovement(CreatedAtMixin, db.Model):
    # FG / Scrap stock ki ledger (RM ki stock_movements jaisi): signed qty + value, kabhi UPDATE / DELETE nahi, galti = ulti row.
    __tablename__ = "fg_movements"

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("fg_batches.id"), nullable=False)
    batch = db.relationship("FGBatch", foreign_keys=[batch_id], backref="movements")
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False)
    warehouse = db.relationship("Warehouse", foreign_keys=[warehouse_id])
    movement_date = db.Column(db.Date, nullable=False)
    movement_type = db.Column(db.String(20), nullable=False)                      # OUTPUT_IN (aage Sales me DISPATCH ...)
    qty = db.Column(db.Float, nullable=False)
    value = db.Column(db.Float, default=0, nullable=False)
    ref_type = db.Column(db.String(12), nullable=False)
    ref_id = db.Column(db.Integer, nullable=False)
    ref_no = db.Column(db.String(30), nullable=True)
    reverses_movement_id = db.Column(db.Integer, db.ForeignKey("fg_movements.id"), nullable=True, unique=True)
    note = db.Column(db.String(255), nullable=True)


@event.listens_for(FGMovement, "before_update")
def _fg_movement_no_update(mapper, connection, target):
    raise RuntimeError("FG stock rows are never edited. Add a reversing row instead.")


@event.listens_for(FGMovement, "before_delete")
def _fg_movement_no_delete(mapper, connection, target):
    raise RuntimeError("FG stock rows are never deleted. Add a reversing row instead.")



class ScrapType(CreatedAtMixin, db.Model):
    # Scrap ki kisme (Metal slag, Burnt flux ...) — dropdown database se (CLAUDE.md rule: koi hardcoded list nahi). Soft-delete / inactive.
    __tablename__ = "scrap_types"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)


class StageLabQC(CreatedAtMixin, db.Model):
    # In-process Lab QC: stage (jaise Melting) ke baad sample lab me. Har round ek row (Fail -> material add -> dobara test). Kabhi delete nahi.
    # Pass round par TC (Test Certificate) file zaroori; wo order / lot ke saath hamesha juda rehta hai.
    __tablename__ = "stage_lab_qc"

    id = db.Column(db.Integer, primary_key=True)
    stage_id = db.Column(db.Integer, db.ForeignKey("production_order_stages.id"), nullable=False)
    stage = db.relationship("ProductionOrderStage", foreign_keys=[stage_id], backref=db.backref("lab_qcs", order_by="StageLabQC.id"))
    tested_at = db.Column(db.DateTime, nullable=False)
    tested_by = db.Column(db.String(60), nullable=False)
    result = db.Column(db.String(20), nullable=False)            # "Pass" / "Need correction" / "Fail"
    remarks = db.Column(db.String(255), nullable=True)
    tc_file = db.Column(db.String(255), nullable=True)           # UPLOAD_FOLDER ke andar ka relative path (Pass par zaroori)
    # Correction me store se jo extra maal auto-issue hua (client meeting 2, #12): [{material, qty, unit, added_by, reason, issue_no}]
    corrections = db.Column(db.JSON, nullable=True)


class Rack(CreatedAtMixin, db.Model):
    # Rack master (client change #10): warehouse ke andar ki jagah (A, B, C / 1, 2, 3 ...). Sirf naam, capacity nahi.
    # Baad me GRN aur FG receipt par rack chunna jayega taaki lot / batch hamesha dhoondha ja sake. Delete nahi, sirf is_deleted (soft).
    __tablename__ = "racks"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(40), nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False)
    warehouse = db.relationship("Warehouse", foreign_keys=[warehouse_id])
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)


class ScrapPack(CreatedAtMixin, db.Model):
    # Scrap pack (client change #8): ek din ka scrap (kai orders ke scrap batches) ek bori / drum me, ek barcode (SCP-YYYYMMDD-001) ke saath.
    # Pack khud stock nahi badalta: stock scrap batch (FGBatch kind SCRAP) me hi rehta hai, pack unhe sirf jodta hai. Unpack = soft (is_deleted), batch wapas free.
    __tablename__ = "scrap_packs"

    id = db.Column(db.Integer, primary_key=True)
    pack_no = db.Column(db.String(20), unique=True, nullable=False)
    pack_date = db.Column(db.Date, nullable=False)                 # kis din ka scrap (batch ki mfg_date)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

    @property
    def batches(self):
        return [item.batch for item in self.items]

    @property
    def weight(self):
        # Pack ka vajan = uske batches ka abhi ka balance (live: output cancel / scrap bik jaye to apne aap badalta hai)
        return round(sum(batch.balance[0] for batch in self.batches), 4)


class ScrapPackItem(CreatedAtMixin, db.Model):
    # Pack me kaun sa scrap batch. Ek batch ek chalte (is_deleted nahi) pack me hi ho sakta hai (routes.py me jaanch).
    __tablename__ = "scrap_pack_items"

    id = db.Column(db.Integer, primary_key=True)
    pack_id = db.Column(db.Integer, db.ForeignKey("scrap_packs.id"), nullable=False)
    pack = db.relationship("ScrapPack", foreign_keys=[pack_id], backref="items")
    batch_id = db.Column(db.Integer, db.ForeignKey("fg_batches.id"), nullable=False)
    batch = db.relationship("FGBatch", foreign_keys=[batch_id])


class Quotation(CreatedAtMixin, db.Model):
    # Sales S1: customer ko bheji jaane wali quotation. Aage chalkar (Finalize) yahi document "Order" ban jaata hai aur Production order banata hai.
    # Revision (rate badalna) isi number ke andar rahegi (revision_no) — alag number nahi. Customer Master se juda hai; lines me product + rate.
    __tablename__ = "quotations"

    id = db.Column(db.Integer, primary_key=True)
    quote_no = db.Column(db.String(20), unique=True, nullable=False)          # QT-2026-001

    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    customer = db.relationship("Customer", foreign_keys=[customer_id])

    quote_date = db.Column(db.Date, nullable=False)
    valid_until = db.Column(db.Date, nullable=True)                           # is date ke baad quotation ka rate valid nahi
    needed_by_date = db.Column(db.Date, nullable=True)                        # customer ko maal kab tak chahiye (Finalize par production order me jaayegi)

    payment_terms_id = db.Column(db.Integer, db.ForeignKey("payment_terms.id"), nullable=True)
    payment_terms = db.relationship("PaymentTerm", foreign_keys=[payment_terms_id])
    delivery_terms = db.Column(db.String(255), nullable=True)                 # jaise "Ex-works, 15 days after PO"
    terms = db.Column(db.String(500), nullable=True)                          # baaki shartein (packing, TC, quality)
    notes = db.Column(db.String(255), nullable=True)                          # andar ke liye note (customer ko print me nahi)

    # Draft -> Sent -> Approved / Rejected ; Draft -> Cancelled. (Approved ke baad Finalize = agla step)
    status = db.Column(db.String(20), default="Draft", nullable=False)
    revision_no = db.Column(db.Integer, default=0, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

    @property
    def is_inter_state(self):
        # Customer ka state aur apni (pehli active) branch ka state alag ho to IGST, warna CGST + SGST
        branch = Branch.query.filter_by(is_deleted=False, is_active=True).order_by(Branch.id).first()
        customer_state = self.customer.state if self.customer else None
        branch_state = branch.state if branch else None
        if customer_state and branch_state and customer_state.id == branch_state.id:
            return False
        return True

    @property
    def summary(self):
        # Quotation ka hisaab ek jagah (list, view, print). Order: line ka discount PEHLE, phir charges (Add / Minus, Charges Master se),
        # phir GST items + charges ke total par (app/tax.py, PO jaisa hi rule).
        tax_lines = [(line.net_value, line.tax_rate.rate_percent if line.tax_rate else 0) for line in self.lines]
        net = 0
        for row in self.charge_rows:
            net += -row["amount"] if row["effect"] == "minus" else row["amount"]
        result = calc_tax(tax_lines, round(net, 2))
        result["cgst"], result["sgst"] = split_tax(result["tax_total"])
        result["inter"] = self.is_inter_state
        result["discount_total"] = round(sum(line.discount_amount for line in self.lines), 2)
        result["gross_total"] = round(sum(line.gross_value for line in self.lines), 2)
        result["charge_rows"] = self.charge_rows
        return result

    @property
    def charge_rows(self):
        # Charges ki list (naam, amount, add / minus) — display aur hisaab dono yahin se
        return [{"name": row.charge.name if row.charge else "Charge", "amount": row.amount, "effect": row.effect} for row in self.charge_lines]


class QuotationLine(CreatedAtMixin, db.Model):
    __tablename__ = "quotation_lines"

    id = db.Column(db.Integer, primary_key=True)
    quotation_id = db.Column(db.Integer, db.ForeignKey("quotations.id"), nullable=False)
    quotation = db.relationship("Quotation", foreign_keys=[quotation_id], backref=db.backref("lines", order_by="QuotationLine.id"))

    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    product = db.relationship("Product", foreign_keys=[product_id])

    qty = db.Column(db.Float, nullable=False)                                 # product ki apni unit me (KG / PCS)
    rate = db.Column(db.Float, nullable=False)                                # per unit, tax se pehle
    discount_percent = db.Column(db.Float, default=0, nullable=False)
    tax_rate_id = db.Column(db.Integer, db.ForeignKey("tax_rates.id"), nullable=True)
    tax_rate = db.relationship("TaxRate", foreign_keys=[tax_rate_id])
    remarks = db.Column(db.String(150), nullable=True)

    @property
    def gross_value(self):
        return line_value(self.qty or 0, self.rate or 0)

    @property
    def discount_amount(self):
        return round(self.gross_value * (self.discount_percent or 0) / 100, 2)

    @property
    def net_value(self):
        # Discount ke baad, GST se pehle
        return round(self.gross_value - self.discount_amount, 2)


class QuotationCharge(CreatedAtMixin, db.Model):
    # Quotation ke charges (Shipping, Labour ...) — Charges Master se, PO ke PurchaseOrderCharge jaisa. effect: "add" total me judta hai, "minus" katta hai.
    __tablename__ = "quotation_charges"

    id = db.Column(db.Integer, primary_key=True)
    quotation_id = db.Column(db.Integer, db.ForeignKey("quotations.id"), nullable=False)
    quotation = db.relationship("Quotation", foreign_keys=[quotation_id], backref=db.backref("charge_lines", order_by="QuotationCharge.id"))
    charge_id = db.Column(db.Integer, db.ForeignKey("charges.id"), nullable=False)
    charge = db.relationship("Charge", foreign_keys=[charge_id])
    amount = db.Column(db.Float, nullable=False)
    effect = db.Column(db.String(10), nullable=False)

