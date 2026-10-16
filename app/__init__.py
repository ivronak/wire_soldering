# Yeh file Flask app banati hai - poore project ka main object.
import os
from flask import Flask, flash, jsonify, redirect, request, url_for
from app.units.routes import units_bp
from app.machines.routes import machines_bp
from app.work_stages.routes import work_stages_bp
from app.rm_categories.routes import rm_categories_bp
from app.raw_materials.routes import raw_materials_bp
from app.tax_rates.routes import tax_rates_bp
from app.product_categories.routes import product_categories_bp
from app.products.routes import products_bp
from app.warehouses.routes import warehouses_bp
from app.vendors.routes import vendors_bp
from app.customers.routes import customers_bp
from app.purchase_orders.routes import purchase_orders_bp
from app.grns.routes import grns_bp
from app.inward_qc.routes import inward_qc_bp
from app.charges.routes import charges_bp
from app.states.routes import states_bp
from app.vendor_types.routes import vendor_types_bp
from app.production_orders.routes import production_orders_bp
from app.payment_terms.routes import payment_terms_bp
from app.party_documents.routes import party_documents_bp
from app.purchase_invoices.routes import purchase_invoices_bp
from app.purchase_returns.routes import purchase_returns_bp
from app.extensions import db, migrate
from app.timeutil import format_ist


def create_app():
    app = Flask(__name__)

    # Flash messages / session ke liye zaroori.
    # Server (VPS) pe ERP_SECRET_KEY environment variable me ek lamba random secret daalna —
    # code me likha hua secret sabko dikhta hai (GitHub pe bhi). Local pe na ho to purana dev key chalega.
    app.config["SECRET_KEY"] = os.environ.get("ERP_SECRET_KEY", "dev-wire-soldering-change-later")

    #SQLite file: instance/erp.db (Flask khud instance/ folder sambhalta hai )
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///erp.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["UPLOAD_FOLDER"] = os.path.join(app.instance_path, "uploads")
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Poori request ki max size (10 MB) — isse bada upload Flask khud hi rok deta hai,
    # file poori server pe aane se pehle. (Party documents ki apni 5 MB limit alag se bhi hai.)
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

    # Templates me {{ x.created_at|ist }} — UTC se India time ("16 Oct 2026, 03:42 PM")
    app.add_template_filter(format_ist, "ist")

    db.init_app(app)
    migrate.init_app(app, db)

    # Models import zaroori - warna create_all ko tables pata nahi chalte
    from app import models 


    # Har module (Blueprint) ko app me jodo — bina register kiye uske URLs kaam nahi karte
    app.register_blueprint(units_bp)
    app.register_blueprint(machines_bp)
    app.register_blueprint(work_stages_bp)
    app.register_blueprint(rm_categories_bp)
    app.register_blueprint(raw_materials_bp)
    app.register_blueprint(tax_rates_bp)
    app.register_blueprint(product_categories_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(warehouses_bp)
    app.register_blueprint(vendors_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(purchase_orders_bp)
    app.register_blueprint(grns_bp)
    app.register_blueprint(inward_qc_bp)
    app.register_blueprint(charges_bp)
    app.register_blueprint(states_bp)
    app.register_blueprint(vendor_types_bp)
    app.register_blueprint(production_orders_bp)
    app.register_blueprint(payment_terms_bp)
    app.register_blueprint(party_documents_bp)
    app.register_blueprint(purchase_invoices_bp)
    app.register_blueprint(purchase_returns_bp)

    @app.route("/")
    def home():
        # Home ab Units pe bhej do — pehla real page
        return redirect(url_for("units.units_list"))

    @app.errorhandler(413)
    def file_too_large(error):
        # 413 = MAX_CONTENT_LENGTH se bada upload. Bina iske user ko ek kachcha error page dikhta.
        # Documents wala upload fetch() (JS) se hota hai aur JSON expect karta hai — usko JSON do,
        # baaki normal forms (jaise PO invoice) ko flash message ke saath wapas bhej do.
        message = "File is too large. The maximum upload size is 10 MB."
        if request.path.startswith("/party_documents"):
            return jsonify(success=False, error=message), 413
        flash(message, "error")
        return redirect(request.referrer or url_for("home"))

    # pehli baar tables banano (agar pehle se hain to kuch nahi bigadta)
    # with app.app_context():
    #     db.create_all()

    return app

app = create_app()
