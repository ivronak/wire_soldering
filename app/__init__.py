# Yeh file Flask app banati hai - poore project ka main object.

from flask import Flask
from app.units.routes import units_bp
from app.machines.routes import machines_bp
from app.work_stages.routes import work_stages_bp
from app.rm_categories.routes import rm_categories_bp
from app.raw_materials.routes import raw_materials_bp
from app.tax_rates.routes import tax_rates_bp
from app.product_categories.routes import product_categories_bp
from app.products.routes import products_bp
from app.extensions import db, migrate


def create_app():
    app = Flask(__name__)

    # Flash messages / session ke liye zaroori (production me strong secret)
    app.config["SECRET_KEY"] = "dev-wire-soldering-change-later"

    #SQLite file: instance/erp.db (Flask khud instance/ folder sambhalta hai )
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///erp.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    migrate.init_app(app, db)

    # Models import zaroori - warna create_all ko tables pata nahi chalte
    from app import models 


    # Abhi ke liye ek test route - sirf yeh check karne ko ki Flask chal raha hai.
    app.register_blueprint(units_bp)
    app.register_blueprint(machines_bp)
    app.register_blueprint(work_stages_bp)
    app.register_blueprint(rm_categories_bp)
    app.register_blueprint(raw_materials_bp)
    app.register_blueprint(tax_rates_bp)
    app.register_blueprint(product_categories_bp)
    app.register_blueprint(products_bp)
    

    @app.route("/")
    def home():
        # Home ab Units pe bhej do — pehla real page
        from flask import redirect, url_for
        return redirect(url_for("units.units_list"))

    # pehli baar tables banano (agar pehle se hain to kuch nahi bigadta)
    with app.app_context():
        db.create_all()

    return app

app = create_app()
