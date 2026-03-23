import os, time, json, logging, threading
import uuid, base64 , hashlib, secrets
import urllib.request, urllib.parse, urllib.error
import db, channels
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, url_for, request, session, jsonify, send_from_directory, abort, g

logger = logging.getLogger(__name__)


_load_env = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_load_env)

_dev_allow_insecure = os.environ.get("DEV_ALLOW_INSECURE_SESSION", "").strip().lower() in {"1", "true", "yes", "on"}
_secret_key = (os.environ.get("SECRET_KEY") or "").strip()
if not _secret_key:
    if _dev_allow_insecure:
        _secret_key = "dev-insecure-placeholder-not-for-production"
        logger.warning(
            "SECRET_KEY not set; using insecure placeholder because DEV_ALLOW_INSECURE_SESSION is enabled (local dev only)"
        )
    else:
        raise RuntimeError(
            "SECRET_KEY environment variable must be set. "
            "For local development only, set DEV_ALLOW_INSECURE_SESSION=1 to use a temporary key."
        )

HACKCLUB_AUTH_BASE = os.environ.get("HACKCLUB_AUTH_BASE", "https://auth.hackclub.com")
HACKCLUB_AUTHORIZE_URL = f"{HACKCLUB_AUTH_BASE}/oauth/authorize"
HACKCLUB_TOKEN_URL = f"{HACKCLUB_AUTH_BASE}/oauth/token"
HACKCLUB_ME_URL = f"{HACKCLUB_AUTH_BASE}/api/v1/me"
HACKCLUB_SCOPES = "openid profile email name slack_id verification_status"

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "").strip()
SLACK_USERS_INFO_URL = "https://slack.com/api/users.info"

app = Flask(__name__, template_folder="../templates", static_folder="../static")
app.secret_key = _secret_key

_cookie_secure_env = os.environ.get("SESSION_COOKIE_SECURE", "").strip().lower()
_cookie_secure = _cookie_secure_env in {"1", "true", "yes", "on"}
if not _cookie_secure:
    app_url = (os.environ.get("APP_URL", "") or "").strip().lower()
    _cookie_secure = app_url.startswith("https://")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=_cookie_secure,
)


ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_MESSAGE_LENGTH = 5000
MAX_QUESTION_LENGTH = 500
MAX_PROJECT_NAME_LENGTH = 200
MAX_PROJECT_DESCRIPTION_LENGTH = 2000

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORAGE_DIR = os.path.join(BASE_DIR, "storage")
UPLOAD_SUBDIR = "uploads"


def _validated_user_content_file(filename):
    safe_path = os.path.normpath(filename)
    if os.path.isabs(safe_path) or safe_path.startswith(".."):
        return None
    check_path = safe_path.replace("\\", "/")
    if not check_path.lower().startswith((UPLOAD_SUBDIR + "/").lower()):
        return None
    _, ext = os.path.splitext(safe_path)
    if ext.lstrip(".").lower() not in ALLOWED_EXTENSIONS:
        return None
    upload_dir = os.path.join(STORAGE_DIR, os.path.dirname(safe_path))
    file_name = os.path.basename(safe_path)
    return upload_dir, file_name


def ensure_csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(24)
        session["csrf_token"] = token
    return token


def _same_origin_ref(ref):
    try:
        if not ref:
            return False
        ref_host = urllib.parse.urlparse(ref).netloc
        return bool(ref_host) and ref_host == request.host
    except Exception:
        return False


@app.before_request
def assign_csp_nonce():
    g.csp_nonce = secrets.token_urlsafe(16)


@app.before_request
def check_auth():
    if request.endpoint == 'static':
        return
    public_endpoints = {'index', 'auth_login', 'auth_callback', 'auth_logout'}
    if request.endpoint in public_endpoints:
        return

    if session.get("user_id"):
        return

    if request.path.startswith("/api/"):
        return jsonify({"error": "unauthorized"}), 401

    return redirect(url_for("index"))

@app.before_request
def csrf_guard():
    ensure_csrf_token()
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    path = request.path
    is_api = path.startswith("/api/")
    is_logout = path == "/auth/logout"
    if not is_api and not is_logout:
        return
    origin = request.headers.get("Origin")
    referer = request.headers.get("Referer")
    if origin and not _same_origin_ref(origin):
        if is_api:
            return jsonify({"error": "forbidden"}), 403
        return redirect(url_for("index"))
    if not origin and referer and not _same_origin_ref(referer):
        if is_api:
            return jsonify({"error": "forbidden"}), 403
        return redirect(url_for("index"))
    token = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
    if not token or token != session.get("csrf_token"):
        if is_api:
            return jsonify({"error": "csrf token invalid"}), 403
        return redirect(url_for("index"))


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    nonce = getattr(g, "csp_nonce", None) or ""
    script_src = f"'self' 'nonce-{nonce}'" if nonce else "'self'"
    response.headers["Content-Security-Policy"] = (
        f"default-src 'self'; script-src {script_src}; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; font-src 'self'; connect-src 'self'; form-action 'self'; frame-ancestors 'none';"
    )
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=(), payment=()"
    return response


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
        "csrf_token": ensure_csrf_token(),
        "csp_nonce": getattr(g, "csp_nonce", "") or "",
    }


active_users = {}
faq_user_messages_by_user = {}
project_submissions_by_user = {}

ACTIVE_TIMEOUT_SEC = 30
PROJECT_SUBMISSION_LIMIT_PER_HOUR = 10
_setup_lock = threading.Lock()


def _ensure_active_user(uid, name, avatar_url=None):
    existing = active_users.get(uid)
    if existing and existing.get("public_id"):
        existing["name"] = name
        existing["last_seen"] = time.time()
        if avatar_url:
            existing["avatar_url"] = avatar_url
        return existing
    entry = {
        "name": name,
        "last_seen": time.time(),
        "public_id": secrets.token_urlsafe(18),
    }
    if avatar_url:
        entry["avatar_url"] = avatar_url
    active_users[uid] = entry
    return entry


def _check_project_submission_rate_limit(user_id):
    now = time.time()
    one_hour_ago = now - 3600

    if user_id not in project_submissions_by_user:
        project_submissions_by_user[user_id] = []

    project_submissions_by_user[user_id] = [
        ts for ts in project_submissions_by_user[user_id]
        if ts > one_hour_ago
    ]

    count = len(project_submissions_by_user[user_id])
    if count >= PROJECT_SUBMISSION_LIMIT_PER_HOUR:
        return False, f"Rate limit exceeded. You can submit {PROJECT_SUBMISSION_LIMIT_PER_HOUR} projects per hour."

    return True, None


def _record_project_submission(user_id):
    now = time.time()
    if user_id not in project_submissions_by_user:
        project_submissions_by_user[user_id] = []
    project_submissions_by_user[user_id].append(now)


def _resolve_active_user_id(any_id):
    if not any_id:
        return None
    if any_id in active_users:
        return any_id
    for uid, data in active_users.items():
        if data.get("public_id") == any_id:
            return uid
    return None


@app.before_request
def setup_once():
    if not getattr(setup_once, "_done", False):
        with _setup_lock:
            if not getattr(setup_once, "_done", False):
                db.setup_tables()
                os.makedirs(os.path.join(STORAGE_DIR, UPLOAD_SUBDIR), exist_ok=True)
                setup_once._done = True


@app.before_request
def ping_active():
    uid = session.get("user_id")
    if uid and request.path.startswith("/app"):
        if uid in active_users:
            active_users[uid]["last_seen"] = time.time()


@app.errorhandler(404)
def not_found(_e):
    logger.warning("404 Not Found: %s %s from %s", request.method, request.path, request.remote_addr)
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
    canonical = (os.environ.get("APP_URL", "").rstrip("/") or request.url_root.rstrip("/"))
    return render_template("index.html", canonical_url=canonical)


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
    oauth_state = secrets.token_urlsafe(24)
    session["oauth_state"] = oauth_state
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": HACKCLUB_SCOPES,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": oauth_state,
    }
    qs = "&".join(f"{k}={urllib.parse.quote(v)}" for k, v in params.items())
    auth_url = f"{HACKCLUB_AUTHORIZE_URL}?{qs}"
    return redirect(auth_url)


@app.route("/auth/logout", methods=["POST"])
def auth_logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/auth/callback")
def auth_callback():
    code = request.args.get("code")
    if not code:
        return redirect(url_for("index"))
    expected_state = session.pop("oauth_state", None)
    got_state = request.args.get("state")
    if not expected_state or not got_state or got_state != expected_state:
        return "Invalid OAuth state", 400
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
        logger.warning("OAuth token HTTPError %s body_prefix=%s", e.code, (err_body[:500] + "…") if len(err_body) > 500 else err_body)
        if session.get("user_id"):
            return redirect(url_for("app_network"))
        if e.code == 403 and "1010" in err_body:
            logger.error(
                "Hack Club Auth redirect URI mismatch (register exact callback URL in developer app). redirect_uri_used=%s",
                redirect_uri,
            )
            return (
                "OAuth configuration error. An admin must register the correct redirect URI with Hack Club Auth. See server logs.",
                400,
            )
        if e.code == 400 and "invalid_grant" in err_body:
            return redirect(url_for("index") + "?auth=retry")
        return "Sign-in could not be completed. Please try again.", 400
    except Exception as e:
        logger.exception("OAuth token exchange failed: %s", e)
        return "Sign-in could not be completed. Please try again later.", 500
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
    try:
        db.save_user(user_id, name, nickname=nickname, slack_id=slack_id, avatar_url=avatar_url)
    except Exception as e:
        logger.exception("auth_callback: save_user failed for user_id=%s: %s", user_id[:16] + "..." if len(user_id) > 16 else user_id, e)
        session.clear()
        return "Database unavailable. Please try again shortly.", 503
    if not db.nickname_for_user(user_id):
        session.clear()
        return "Database unavailable. Please try again shortly.", 503
    session.clear()
    session["user_id"] = user_id
    session["name"] = name
    session["nickname"] = nickname
    session["slack_id"] = slack_id
    session["csrf_token"] = secrets.token_urlsafe(24)
    session.permanent = True
    _ensure_active_user(user_id, nickname, avatar_url=avatar_url)
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


def _combined_hardcoded_messages(viewer_id, user_id):
    if user_id not in channels.HARDCODED_DMS:
        return []
    hardcoded = list(channels.HARDCODED_DMS.get(user_id, []))
    custom = db.get_custom_dm_messages(viewer_id, user_id)
    return hardcoded + custom


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

        allowed, reason = _check_project_submission_rate_limit(user_id)
        if not allowed:
            return jsonify({"error": reason}), 429

        submitted_by = session.get("nickname") or session.get("name") or "You"
        slack_id = session.get("slack_id")
        db.upsert_user(user_id, session.get("name") or "", nickname=submitted_by, slack_id=slack_id)
        name = (request.form.get("name") or "").strip()
        description = (request.form.get("description") or "").strip()
        if not name:
            return jsonify({"error": "Project name is required"}), 400
        if len(name) > MAX_PROJECT_NAME_LENGTH:
            return jsonify({"error": f"Project name too long. Maximum {MAX_PROJECT_NAME_LENGTH} characters."}), 400
        if not description:
            return jsonify({"error": "Description is required"}), 400
        if len(description) > MAX_PROJECT_DESCRIPTION_LENGTH:
            return jsonify({"error": f"Description too long. Maximum {MAX_PROJECT_DESCRIPTION_LENGTH} characters."}), 400
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

        upload_dir = os.path.join(STORAGE_DIR, UPLOAD_SUBDIR)
        os.makedirs(upload_dir, exist_ok=True)
        path = os.path.join(upload_dir, safe_name)
        try:
            file.save(path)
        except Exception:
            return jsonify({"error": "Failed to save upload"}), 500

        screenshot_path = UPLOAD_SUBDIR + "/" + safe_name
        if not db.get_db():
            return jsonify({"error": "Database unavailable. Try again later."}), 503
        pid = db.add_project(name, description, screenshot_path, submitted_by, submitted_by_user_id=user_id, submitted_by_slack_id=slack_id)
        if not pid:
            return jsonify({"error": "Failed to save project"}), 500
        _record_project_submission(user_id)
        return jsonify({"ok": True, "message": "Thanks! Your project is pending approval. You'll get stickers once it's approved!"})
    except Exception:
        logger.exception("api_what_people_are_making_submit failed")
        return jsonify({"error": "Failed to submit. Try again later."}), 500


@app.route("/api/what-people-are-making", methods=["GET"])
def api_what_people_are_making_list():
    if not session.get("user_id"):
        return jsonify({"error": "unauthorized"}), 401
    projects = projects_for_page()
    public = []
    for p in projects:
        row = {k: v for k, v in p.items() if k != "submitted_by_slack_id"}
        public.append(row)
    return jsonify({"projects": public})




@app.route("/user_content/<path:filename>")
def served_content(filename):
    if not session.get("user_id"):
        abort(403)
    resolved = _validated_user_content_file(filename)
    if not resolved:
        abort(404)
    upload_dir, file_name = resolved
    if not os.path.exists(os.path.join(upload_dir, file_name)):
        abort(404)
    return send_from_directory(upload_dir, file_name, conditional=True)

@app.route("/app/dm/<user_id>")
def app_dm(user_id):
    if not session.get("user_id"):
        return redirect(url_for("index"))
    if user_id not in channels.HARDCODED_DMS:
        return redirect(url_for("app_network"))
    viewer_id = session.get("user_id")
    messages = _combined_hardcoded_messages(viewer_id, user_id)
    display_name = channels.HARDCODED_DM_NAMES.get(user_id, user_id)
    return render_template("dm.html", dm_user_id=user_id, dm_display_name=display_name, messages=messages)


@app.route("/app/dm/live/<other_id>")
def app_dm_live(other_id):
    me_id = session.get("user_id")
    if not me_id:
        return redirect(url_for("index"))
    remove_stale()
    target_id = _resolve_active_user_id(other_id)
    if not target_id or target_id == me_id:
        return redirect(url_for("app_network"))
    other = active_users.get(target_id, {})
    other_name = other.get("name") or "Unknown"
    return render_template("dm_live.html", other_id=other.get("public_id", other_id), other_name=other_name)


@app.route("/api/dm/live/<other_id>", methods=["GET"])
def api_dm_live_get(other_id):
    me_id = session.get("user_id")
    if not me_id:
        return jsonify({"error": "unauthorized"}), 401
    remove_stale()
    target_id = _resolve_active_user_id(other_id)
    if not target_id or target_id == me_id:
        return jsonify({"error": "not found"}), 404
    if target_id not in active_users:
        return jsonify({"error": "not found"}), 404
    messages = db.messages_between(me_id, target_id)
    return jsonify({"messages": messages})


@app.route("/api/dm/live/<other_id>", methods=["POST"])
def api_dm_live_post(other_id):
    me_id = session.get("user_id")
    me_name = session.get("nickname") or session.get("name") or "You"
    if not me_id:
        return jsonify({"error": "unauthorized"}), 401
    remove_stale()
    target_id = _resolve_active_user_id(other_id)
    if not target_id or target_id == me_id:
        return jsonify({"error": "not found"}), 404
    if target_id not in active_users:
        return jsonify({"error": "not found"}), 404
    data = request.get_json() or {}
    msg = (data.get("message") or "").strip()
    if not msg:
        return jsonify({"error": "empty message"}), 400
    if len(msg) > MAX_MESSAGE_LENGTH:
        return jsonify({"error": f"Message too long. Maximum {MAX_MESSAGE_LENGTH} characters."}), 400
    if not db.add_dm_message(me_id, me_name, target_id, msg):
        return jsonify({"error": "Failed to save message"}), 500
    return jsonify({"ok": True, "message": {"from": me_name, "message": msg}})


@app.route("/api/users/active")
def api_active_users():
    if not session.get("user_id"):
        return jsonify({"error": "unauthorized"}), 401
    remove_stale()
    me_id = session.get("user_id")
    users = []
    for uid, data in active_users.items():
        if uid == me_id:
            continue
        users.append({
            "id": data.get("public_id"),
            "name": data["name"],
            "avatar_url": data.get("avatar_url")
        })
    return jsonify({"users": users})


@app.route("/api/users/heartbeat", methods=["POST"])
def api_heartbeat():
    uid = session.get("user_id")
    if not uid:
        return jsonify({"error": "unauthorized"}), 401
    name = session.get("nickname") or session.get("name") or "User"
    _ensure_active_user(uid, name)
    return jsonify({"ok": True})


@app.route("/api/dm/<user_id>", methods=["GET"])
def api_dm_get(user_id):
    viewer_id = session.get("user_id")
    if not viewer_id:
        return jsonify({"error": "unauthorized"}), 401
    if user_id not in channels.HARDCODED_DMS:
        return jsonify({"error": "not found"}), 404
    hardcoded = list(channels.HARDCODED_DMS.get(user_id, []))
    custom = db.get_custom_dm_messages(viewer_id, user_id)
    messages = hardcoded + custom
    return jsonify({"messages": messages})


@app.route("/api/dm/<user_id>", methods=["POST"])
def api_dm_post(user_id):
    viewer_id = session.get("user_id")
    viewer_name = session.get("nickname") or session.get("name") or "You"
    if not viewer_id:
        return jsonify({"error": "unauthorized"}), 401
    if user_id not in channels.HARDCODED_DMS:
        return jsonify({"error": "not found"}), 404
    data = request.get_json() or {}
    msg = (data.get("message") or "").strip()
    if not msg:
        return jsonify({"error": "empty message"}), 400
    if len(msg) > MAX_MESSAGE_LENGTH:
        return jsonify({"error": f"Message too long. Maximum {MAX_MESSAGE_LENGTH} characters."}), 400
    msg_id = db.add_custom_dm_message(viewer_id, user_id, viewer_name, msg)
    if msg_id is None:
        return jsonify({"error": "Failed to save message"}), 500
    return jsonify({"ok": True, "message": {"from": viewer_name, "message": msg}})


@app.route("/api/network-faq", methods=["POST"])
def api_network_faq_post():
    if not session.get("user_id"):
        return jsonify({"error": "unauthorized"}), 401
    uid = session.get("user_id")
    me = session.get("nickname") or session.get("name") or "You"
    data = request.get_json() or {}
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "empty question"}), 400
    if len(question) > MAX_QUESTION_LENGTH:
        return jsonify({"error": f"Question too long. Maximum {MAX_QUESTION_LENGTH} characters."}), 400
    heidi_reply = ""
    for q in channels.NETWORK_FAQ_QUESTIONS:
        if q["question"] == question:
            heidi_reply = q["reply"]
            break
    if not heidi_reply:
        heidi_reply = "Thanks for asking! I'll get back to you on that."
    pair = db.add_faq_user_and_heidi(uid, me, question, "Heidi", heidi_reply)
    if pair is None:
        return jsonify({"error": "Failed to save FAQ exchange"}), 500
    return jsonify({"ok": True, "user_message": {"from": me, "message": question}, "heidi_reply": {"from": "Heidi", "message": heidi_reply}})


@app.route("/api/network-faq/extra")
def api_network_faq_extra():
    uid = session.get("user_id")
    if not uid:
        return jsonify({"error": "unauthorized"}), 401
    messages = db.get_faq_messages(uid)
    return jsonify({"messages": messages})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "53000")), debug=False, use_reloader=False)