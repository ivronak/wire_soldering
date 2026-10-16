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

class Machines(CreatedAtMixin, db.Model):
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

class WorkStage(CreatedAtMixin, db.Model):
    __tablename__="work_stage"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False) 
    name = db.Column(db.String(100), nullable=False)
    #  Chhota number = pehle stage (cutting=10, soldering=20...)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

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

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

    @property
    def active_variants(self):
        return [v for v in self.variants if not v.is_deleted]

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

    order_date = db.Column(db.Date, nullable=False)
    planned_qty = db.Column(db.Float, nullable=False)
    # KG product pe 1. Doosri unit pe ek piece ka weight, taaki batch KG nikal sake.
    unit_weight = db.Column(db.Float, default=1, nullable=False)
    status = db.Column(db.String(20), default="Draft", nullable=False)
    remarks = db.Column(db.String(255), nullable=True)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)


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