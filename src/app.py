import os, time, json, logging, threading
import uuid, base64 , hashlib, secrets
import urllib.request, urllib.parse, urllib.error
import db, channels

logger = logging.getLogger(__name__)
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, url_for, request, session, jsonify


_load_env = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_load_env)

HACKCLUB_AUTH_BASE = os.environ.get("HACKCLUB_AUTH_BASE", "https://auth.hackclub.com")
HACKCLUB_AUTHORIZE_URL = f"{HACKCLUB_AUTH_BASE}/oauth/authorize"
HACKCLUB_TOKEN_URL = f"{HACKCLUB_AUTH_BASE}/oauth/token"
HACKCLUB_ME_URL = f"{HACKCLUB_AUTH_BASE}/api/v1/me"
HACKCLUB_SCOPES = "openid profile email name slack_id verification_status"

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "").strip()
SLACK_USERS_INFO_URL = "https://slack.com/api/users.info"

app = Flask(__name__, template_folder="../templates", static_folder="../static")
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")

UPLOAD_SUBDIR = "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


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


active_users = {}
faq_user_messages = []

ACTIVE_TIMEOUT_SEC = 30
_setup_lock = threading.Lock()


@app.before_request
def setup_once():
    if not getattr(setup_once, "_done", False):
        with _setup_lock:
            if not getattr(setup_once, "_done", False):
                db.setup_tables()
                os.makedirs(os.path.join(app.static_folder, UPLOAD_SUBDIR), exist_ok=True)
                setup_once._done = True


@app.before_request
def ping_active():
    uid = session.get("user_id")
    if uid and request.path.startswith("/app"):
        if uid in active_users:
            active_users[uid]["last_seen"] = time.time()


@app.errorhandler(404)
def not_found(_e):
    return redirect(url_for("index"))


def remove_stale():
    now = time.time()
    expired = [uid for uid, data in active_users.items() if now - data["last_seen"] > ACTIVE_TIMEOUT_SEC]
    for uid in expired:
        del active_users[uid]


def fetch_slack_profile(slack_id):
    if not SLACK_BOT_TOKEN or not slack_id:
        return (None, None)
    try:
        req = urllib.request.Request(
            f"{SLACK_USERS_INFO_URL}?user={urllib.parse.quote(slack_id)}",
            headers={
                "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
                "User-Agent": "YSWS/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        if not data.get("ok"):
            return (None, None)
        user = data.get("user") or {}
        profile = user.get("profile") or {}
        display_name = (
            profile.get("display_name")
            or profile.get("real_name")
            or user.get("real_name")
            or user.get("name")
            or None
        )
        avatar_url = (
            profile.get("image_72")
            or profile.get("image_48")
            or profile.get("image_32")
            or None
        )
        if display_name or avatar_url:
            db.save_profile_for_slack(slack_id, display_name, avatar_url)
        if display_name and not db.nickname_for_slack(slack_id):
            db.save_user_from_slack(slack_id, display_name, avatar_url)
        return (display_name, avatar_url)
    except Exception as e:
        logger.exception("fetch_slack_profile: Failed for slack_id=%s: %s", slack_id[:8] + "..." if len(slack_id) > 8 else slack_id, e)
        return (None, None)


def display_name_for_slack(slack_id):
    if not slack_id:
        return None
    nickname = db.nickname_for_slack(slack_id)
    if nickname:
        return nickname
    display_name, _ = fetch_slack_profile(slack_id)
    return display_name


def avatar_for_slack(slack_id):
    if not slack_id:
        return None
    url = db.avatar_for_slack(slack_id)
    if url:
        return url
    _, avatar_url = fetch_slack_profile(slack_id)
    return avatar_url


def login_redirect_url():
    explicit = os.environ.get("HACKCLUB_REDIRECT_URI", "").strip()
    if explicit:
        return explicit
    base = os.environ.get("APP_URL", "").rstrip("/")
    if not base:
        base = request.host_url.rstrip("/")
    return f"{base}{url_for('auth_callback')}"


@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("app_network"))
    return render_template("index.html")


@app.route("/auth/login")
def auth_login():
    if session.get("user_id"):
        return redirect(url_for("app_network"))
    client_id = os.environ.get("HACKCLUB_CLIENT_ID")
    if not client_id:
        return "HACKCLUB_CLIENT_ID not configured", 500
    redirect_uri = login_redirect_url()
    code_verifier = secrets.token_urlsafe(32)
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).decode().rstrip("=")
    session["oauth_code_verifier"] = code_verifier
    session["oauth_redirect_uri"] = redirect_uri
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": HACKCLUB_SCOPES,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    qs = "&".join(f"{k}={urllib.parse.quote(v)}" for k, v in params.items())
    auth_url = f"{HACKCLUB_AUTHORIZE_URL}?{qs}"
    return redirect(auth_url)


@app.route("/auth/logout")
def auth_logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/auth/callback")
def auth_callback():
    code = request.args.get("code")
    if not code:
        return redirect(url_for("index"))
    client_id = os.environ.get("HACKCLUB_CLIENT_ID")
    client_secret = os.environ.get("HACKCLUB_CLIENT_SECRET")
    if not client_id or not client_secret:
        return "Hack Club Auth not configured", 500
    redirect_uri = session.pop("oauth_redirect_uri", None) or login_redirect_url()
    code_verifier = session.pop("oauth_code_verifier", None)
    body_params = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "code": code,
        "redirect_uri": redirect_uri,
    }
    if code_verifier:
        body_params["code_verifier"] = code_verifier
    body = urllib.parse.urlencode(body_params).encode()
    req = urllib.request.Request(HACKCLUB_TOKEN_URL, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("User-Agent", "Mozilla/5.0 (compatible; YSWS/1.0)")
    req.add_header("Accept", "application/json")
    creds_b64 = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    req.add_header("Authorization", f"Basic {creds_b64}")
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode() if e.fp else ""
        if session.get("user_id"):
            return redirect(url_for("app_network"))
        if e.code == 403 and "1010" in err_body:
            return (
                f"Auth token error: {e.code} {err_body}<br><br>"
                f"<strong>Fix:</strong> In your <a href='https://auth.hackclub.com/developer_apps'>Hack Club Developer App</a>, "
                f"add this <strong>exact</strong> Redirect URI (no trailing slash):<br>"
                f"<code>{redirect_uri}</code>",
                400,
            )
        if e.code == 400 and "invalid_grant" in err_body:
            return redirect(url_for("index") + "?auth=retry")
        return f"Auth token error: {e.code} {err_body}", 400
    except Exception as e:
        return f"Auth error: {e}", 500
    access_token = data.get("access_token")
    if not access_token:
        return "No access token in response", 400
    me_req = urllib.request.Request(HACKCLUB_ME_URL)
    me_req.add_header("Authorization", f"Bearer {access_token}")
    me_req.add_header("User-Agent", "Mozilla/5.0 (compatible; YSWS/1.0)")
    me_req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(me_req) as resp:
            me_data = json.loads(resp.read().decode())
    except urllib.error.HTTPError:
        return "Failed to fetch user info", 400
    identity = me_data.get("identity") or {}
    user_id = identity.get("id") or identity.get("slack_id") or ""
    slack_id = identity.get("slack_id")
    first = identity.get("first_name") or ""
    last = identity.get("last_name") or ""
    name = f"{first} {last}".strip() or identity.get("primary_email") or "You"
    if not user_id:
        return "No user id in profile", 400
    nickname = name
    avatar_url = None
    if slack_id:
        slack_nickname, avatar_url = fetch_slack_profile(slack_id)
        if slack_nickname:
            nickname = slack_nickname
        else:
            logger.warning("auth_callback: Could not fetch Slack display name for slack_id=%s, using real name", slack_id[:8] + "..." if len(slack_id) > 8 else slack_id)
    session["user_id"] = user_id
    session["name"] = name
    session["nickname"] = nickname
    session["slack_id"] = slack_id
    session.permanent = True
    try:
        db.save_user(user_id, name, nickname=nickname, slack_id=slack_id, avatar_url=avatar_url)
    except Exception as e:
        logger.exception("auth_callback: save_user failed for user_id=%s: %s", user_id[:16] + "..." if len(user_id) > 16 else user_id, e)
    active_users[user_id] = {"name": nickname, "last_seen": time.time()}
    return redirect(url_for("app_network"))


@app.route("/app")
def app_index():
    if not session.get("user_id"):
        return redirect(url_for("index"))
    return redirect(url_for("app_network"))


@app.route("/app/network")
def app_network():
    if not session.get("user_id"):
        return redirect(url_for("index"))
    return render_template("network.html", network_replies=channels.NETWORK_FOLLOWUP_REPLIES, network_first_question=channels.NETWORK_FIRST_QUESTION_OPTIONS)


@app.route("/app/network-faq")
def app_network_faq():
    if not session.get("user_id"):
        return redirect(url_for("index"))
    return render_template("network_faq.html", existing=channels.NETWORK_FAQ_EXISTING, questions=channels.NETWORK_FAQ_QUESTIONS)


@app.route("/app/network-announcements")
def app_network_announcements():
    if not session.get("user_id"):
        return redirect(url_for("index"))
    return render_template("network_announcements.html", announcements=channels.NETWORK_ANNOUNCEMENTS)


def projects_for_page():
    raw = db.approved_projects() if db.get_db() else []
    for p in raw:
        sid = p.get("submitted_by_slack_id")
        if sid:
            resolved = display_name_for_slack(sid)
            if resolved:
                p["submitted_by"] = resolved
    return raw


@app.route("/app/what-people-are-making")
def app_what_people_are_making():
    if not session.get("user_id"):
        return redirect(url_for("index"))
    projects = projects_for_page()
    return render_template("what_people_are_making.html", projects=projects)


def is_allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/api/what-people-are-making", methods=["POST"])
def api_what_people_are_making_submit():
    try:
        if not session.get("user_id"):
            return jsonify({"error": "unauthorized"}), 401
        user_id = session.get("user_id")
        submitted_by = session.get("nickname") or session.get("name") or "You"
        slack_id = session.get("slack_id")
        db.upsert_user(user_id, session.get("name") or "", nickname=submitted_by, slack_id=slack_id)
        name = (request.form.get("name") or "").strip()
        description = (request.form.get("description") or "").strip()
        if not name:
            return jsonify({"error": "Project name is required"}), 400
        if not description:
            return jsonify({"error": "Description is required"}), 400
        if "screenshot" not in request.files:
            return jsonify({"error": "Screenshot is required"}), 400
        file = request.files["screenshot"]
        if not file or not file.filename:
            return jsonify({"error": "Screenshot is required"}), 400
        if not is_allowed_file(file.filename):
            return jsonify({"error": "Invalid image type. Use PNG, JPG, GIF, or WebP."}), 400
        file.seek(0, 2)
        size = file.tell()
        file.seek(0)
        if size > MAX_UPLOAD_BYTES:
            return jsonify({"error": "Image must be under 5MB"}), 400
        ext = file.filename.rsplit(".", 1)[1].lower()
        safe_name = str(uuid.uuid4()) + "." + ext
        upload_dir = os.path.join(app.static_folder, UPLOAD_SUBDIR)
        os.makedirs(upload_dir, exist_ok=True)
        path = os.path.join(upload_dir, safe_name)
        try:
            file.save(path)
        except Exception:
            return jsonify({"error": "Failed to save upload"}), 500
        screenshot_path = UPLOAD_SUBDIR + "/" + safe_name
        if not db.get_db():
            err = db.get_db_error() or "Unknown"
            return jsonify({"error": "Database unavailable. Try again later.", "detail": err}), 503
        pid = db.add_project(name, description, screenshot_path, submitted_by, submitted_by_user_id=user_id, submitted_by_slack_id=slack_id)
        if not pid:
            return jsonify({"error": "Failed to save project"}), 500
        return jsonify({"ok": True, "message": "Thanks! Your project is pending approval. You'll get stickers once it's approved!"})
    except Exception as e:
        return jsonify({"error": "Failed to submit. Try again later.", "detail": str(e)}), 500


@app.route("/api/what-people-are-making", methods=["GET"])
def api_what_people_are_making_list():
    if not session.get("user_id"):
        return jsonify({"error": "unauthorized"}), 401
    projects = projects_for_page()
    return jsonify({"projects": projects})


@app.route("/app/dm/<user_id>")
def app_dm(user_id):
    if not session.get("user_id"):
        return redirect(url_for("index"))
    if user_id not in channels.HARDCODED_DMS:
        return redirect(url_for("app_network"))
    messages = list(channels.HARDCODED_DMS[user_id])
    display_name = channels.HARDCODED_DM_NAMES.get(user_id, user_id)
    return render_template("dm.html", dm_user_id=user_id, dm_display_name=display_name, messages=messages)


@app.route("/app/dm/live/<other_id>")
def app_dm_live(other_id):
    if not session.get("user_id"):
        return redirect(url_for("index"))
    other = active_users.get(other_id, {})
    other_name = other.get("name") or db.nickname_for_user(other_id) or "Unknown"
    return render_template("dm_live.html", other_id=other_id, other_name=other_name)


@app.route("/api/users/active")
def api_active_users():
    remove_stale()
    me_id = session.get("user_id")
    users = []
    for uid, data in active_users.items():
        if uid == me_id:
            continue
        slack_id, avatar_url = db.slack_and_avatar_for_user(uid)
        if slack_id and not avatar_url:
            avatar_url = avatar_for_slack(slack_id)
        users.append({"id": uid, "name": data["name"], "avatar_url": avatar_url})
    return jsonify({"users": users})


@app.route("/api/users/heartbeat", methods=["POST"])
def api_heartbeat():
    uid = session.get("user_id")
    name = session.get("nickname") or session.get("name") or "User"
    if uid and name:
        if uid not in active_users:
            active_users[uid] = {"name": name, "last_seen": time.time()}
        else:
            active_users[uid]["last_seen"] = time.time()
    return jsonify({"ok": True})


@app.route("/api/dm/<user_id>", methods=["GET"])
def api_dm_get(user_id):
    if user_id not in channels.HARDCODED_DMS:
        return jsonify({"error": "not found"}), 404
    messages = list(channels.HARDCODED_DMS[user_id])
    return jsonify({"messages": messages})


@app.route("/api/dm/live/<other_id>", methods=["GET"])
def api_dm_live_get(other_id):
    me_id = session.get("user_id")
    if not me_id:
        return jsonify({"error": "unauthorized"}), 401
    out = db.messages_between(me_id, other_id)
    return jsonify({"messages": out})


@app.route("/api/dm/live/<other_id>", methods=["POST"])
def api_dm_live_post(other_id):
    me_id = session.get("user_id")
    me_name = session.get("nickname") or session.get("name") or "You"
    if not me_id:
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json() or {}
    msg = (data.get("message") or "").strip()
    if not msg:
        return jsonify({"error": "empty message"}), 400
    db.add_dm_message(me_id, me_name, other_id, msg)
    return jsonify({"ok": True, "message": {"from": me_name, "message": msg}})


@app.route("/api/network-faq", methods=["POST"])
def api_network_faq_post():
    if not session.get("user_id"):
        return jsonify({"error": "unauthorized"}), 401
    me = session.get("nickname") or session.get("name") or "You"
    data = request.get_json() or {}
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "empty question"}), 400
    heidi_reply = ""
    for q in channels.NETWORK_FAQ_QUESTIONS:
        if q["question"] == question:
            heidi_reply = q["reply"]
            break
    if not heidi_reply:
        heidi_reply = "Thanks for asking! I'll get back to you on that."
    faq_user_messages.append({"from": me, "message": question})
    faq_user_messages.append({"from": "Heidi", "message": heidi_reply})
    return jsonify({"ok": True, "user_message": {"from": me, "message": question}, "heidi_reply": {"from": "Heidi", "message": heidi_reply}})


@app.route("/api/network-faq/extra")
def api_network_faq_extra():
    return jsonify({"messages": list(faq_user_messages)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "53000")), debug=False, use_reloader=False)