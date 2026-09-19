# Ye file server start karne ke liye hai - isi ko "python run.py" se chalate hai

from app import app

if __name__ == "__main__":
    app.run(debug=True)