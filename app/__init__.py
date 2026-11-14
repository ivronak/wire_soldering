# Yeh file Flask app banati hai - poore project ka main object.
import os
from flask import Flask, flash, jsonify, redirect, request, url_for
from app.units.routes import units_bp
from app.dashboard.routes import dashboard_bp
from app.machines.routes import machines_bp
from app.production_lines.routes import production_lines_bp
from app.work_stages.routes import work_stages_bp
from app.rm_categories.routes import rm_categories_bp
from app.raw_materials.routes import raw_materials_bp
from app.tax_rates.routes import tax_rates_bp
from app.product_categories.routes import product_categories_bp
from app.products.routes import products_bp
from app.warehouses.routes import warehouses_bp
from app.racks.routes import racks_bp
from app.material_plan.routes import material_plan_bp
from app.vendors.routes import vendors_bp
from app.customers.routes import customers_bp
from app.purchase_orders.routes import purchase_orders_bp
from app.grns.routes import grns_bp
from app.inward_qc.routes import inward_qc_bp
from app.charges.routes import charges_bp
from app.states.routes import states_bp
from app.vendor_types.routes import vendor_types_bp
from app.production_orders.routes import production_orders_bp
from app.production_planning.routes import production_planning_bp
from app.costing.routes import costing_bp
from app.payment_terms.routes import payment_terms_bp
from app.party_documents.routes import party_documents_bp
from app.purchase_invoices.routes import purchase_invoices_bp
from app.purchase_returns.routes import purchase_returns_bp
from app.inventory.routes import inventory_bp
from app.material_issues.routes import material_issues_bp
from app.routing.routes import routing_bp
from app.production_output.routes import production_output_bp
from app.scrap.routes import scrap_bp
from app.variance.routes import variance_bp
from app.tour.routes import tour_bp
from app.stock_transfers.routes import stock_transfers_bp
from app.stock_adjustments.routes import stock_adjustments_bp
from app.opening_stock.routes import opening_stock_bp
from app.inventory.alerts import alert_count
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
    from datetime import date as _date
    app.add_template_global(lambda: _date.today(), "today_date")
    # Category ke flat icons (app/icons.py): {{ icon_tile(product.category.icon, 40) }}
    from app.icons import icon_choices, icon_svg, icon_tile
    app.add_template_global(icon_tile, "icon_tile")
    app.add_template_global(icon_svg, "icon_svg")
    app.add_template_global(icon_choices, "icon_choices")

    db.init_app(app)
    migrate.init_app(app, db)

    # Models import zaroori - warna create_all ko tables pata nahi chalte
    from app import models 


    # Har module (Blueprint) ko app me jodo — bina register kiye uske URLs kaam nahi karte
    app.register_blueprint(units_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(machines_bp)
    app.register_blueprint(production_lines_bp)
    app.register_blueprint(work_stages_bp)
    app.register_blueprint(rm_categories_bp)
    app.register_blueprint(raw_materials_bp)
    app.register_blueprint(tax_rates_bp)
    app.register_blueprint(product_categories_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(warehouses_bp)
    app.register_blueprint(racks_bp)
    app.register_blueprint(material_plan_bp)
    app.register_blueprint(vendors_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(purchase_orders_bp)
    app.register_blueprint(grns_bp)
    app.register_blueprint(inward_qc_bp)
    app.register_blueprint(charges_bp)
    app.register_blueprint(states_bp)
    app.register_blueprint(vendor_types_bp)
    app.register_blueprint(production_orders_bp)
    app.register_blueprint(production_planning_bp)
    app.register_blueprint(costing_bp)
    app.register_blueprint(payment_terms_bp)
    app.register_blueprint(party_documents_bp)
    app.register_blueprint(purchase_invoices_bp)
    app.register_blueprint(purchase_returns_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(material_issues_bp)
    app.register_blueprint(routing_bp)
    app.register_blueprint(production_output_bp)
    app.register_blueprint(scrap_bp)
    app.register_blueprint(variance_bp)
    app.register_blueprint(tour_bp)
    app.register_blueprint(stock_transfers_bp)
    app.register_blueprint(stock_adjustments_bp)
    app.register_blueprint(opening_stock_bp)

    # Sidebar me Stock ledger ke saamne lal ginti: kitne materials ka reorder / minimum level aa gaya (app/inventory/alerts.py)
    @app.context_processor
    def inject_stock_alert_count():
        return {"stock_alert_count": alert_count()}

    # "flask inventory-backfill": inventory banne se pehle ke GRN / QC / Return ki stock rows banata hai (dobara chalao to double nahi hoga)
    @app.cli.command("inventory-backfill")
    def inventory_backfill_command():
        from app.inventory.posting import backfill
        problems = backfill()
        print("Inventory backfill done.")
        for problem in problems:
            print("NOTE:", problem)

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
