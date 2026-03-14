import os
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, render_template, request
import db
import channels

_load_env = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_load_env)

app = Flask(__name__, template_folder="../templates", static_folder="../static")
app.secret_key = os.environ.get("SECRET_KEY", "dev")
UPLOAD_SUBDIR = "uploads"

@app.before_request
def setup_once():
    if not getattr(setup_once, "_done", False):
        db.setup_tables()
        os.makedirs(os.path.join(app.static_folder, UPLOAD_SUBDIR), exist_ok=True)
        setup_once._done = True

@app.context_processor
def sidebar_context():
    active_dm = request.view_args.get("user_id") if request.view_args else None
    return {
        "external_channels": channels.EXTERNAL_CHANNELS,
        "slack_base": channels.SLACK_BASE,
        "hardcoded_dm_names": channels.HARDCODED_DM_NAMES,
        "avatars": channels.AVATARS,
        "active_dm": active_dm,
        "request": request,
    }

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
