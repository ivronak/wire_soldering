# Yeh file Flask app banati hai - poore project ka main object.

from flask import Flask
from app.units.routes import units_bp


app = Flask(__name__)

# Abhi ke liye ek test route - sirf yeh check karne ko ki Flask chal raha hai.

app.register_blueprint(units_bp)
@app.route("/")
def hello():
    return "Hello, World! Flask app chal rahi hai."
