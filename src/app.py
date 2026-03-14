import os
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, render_template

_load_env = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_load_env)

app = Flask(__name__, template_folder="../templates", static_folder="../static")
app.secret_key = os.environ.get("SECRET_KEY", "dev")

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
