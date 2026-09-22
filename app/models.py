from app.extensions import db

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

    category = db.relationship("RmCategories", foreign_keys=[category_id])
    base_unit = db.relationship("Unit", foreign_keys=[base_unit_id])
    alt_unit = db.relationship("Unit", foreign_keys=[alt_unit_id])

    conversion_note = db.Column(db.String(100), nullable=True)
    reorder_level = db.Column(db.Integer, nullable=True)
    min_stock = db.Column(db.Integer, nullable=True)
    max_stock = db.Column(db.Integer, nullable=True)
    hsn_code = db.Column(db.String(8), nullable=True)

    valuation_method = db.Column(db.String(20), default='fifo', nullable=False)

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
