import os

_db = None
_last_connection_error = None


def get_db_error():
    return _last_connection_error


def get_db():
    global _db, _last_connection_error
    if _db is None:
        _last_connection_error = None
        try:
            import psycopg2
            host = os.environ.get("DB_HOST", "").strip()
            port = os.environ.get("DB_PORT", "5432").strip()
            dbname = os.environ.get("DB_NAME", "").strip()
            user = os.environ.get("DB_USER", "").strip()
            password = os.environ.get("DB_PASSWORD", "").strip()
            sslmode = os.environ.get("DB_SSLMODE", "").strip() or None
            if host and dbname and user:
                kwargs = dict(
                    host=host,
                    port=int(port) if port else 5432,
                    dbname=dbname,
                    user=user,
                    password=password,
                )
                if sslmode:
                    kwargs["sslmode"] = sslmode
                _db = psycopg2.connect(**kwargs)
            else:
                url = os.environ.get("DATABASE_URL")
                if not url:
                    _last_connection_error = "DB_HOST, DB_NAME, DB_USER (or DATABASE_URL) not set"
                    _db = None
                else:
                    _db = psycopg2.connect(url)
            if _db:
                _db.autocommit = False
        except Exception as e:
            _last_connection_error = str(e)
            _db = None
    return _db


def setup_tables():
    conn = get_db()
    if not conn:
        return
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            nickname TEXT NOT NULL DEFAULT 'User',
            slack_id TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS nickname TEXT DEFAULT 'User'")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url TEXT")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            screenshot_path TEXT NOT NULL,
            submitted_by TEXT NOT NULL,
            approved BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    cur.execute("ALTER TABLE projects ADD COLUMN IF NOT EXISTS submitted_by_user_id TEXT")
    cur.execute("ALTER TABLE projects ADD COLUMN IF NOT EXISTS submitted_by_slack_id TEXT")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS dm_messages (
            id SERIAL PRIMARY KEY,
            from_user_id TEXT NOT NULL,
            from_user_name TEXT NOT NULL,
            to_user_id TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()


def save_user(user_id, name, nickname=None, slack_id=None, avatar_url=None):
    if nickname is None:
        nickname = name
    conn = get_db()
    if not conn:
        return
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO users (id, name, nickname, slack_id, avatar_url, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                nickname = COALESCE(NULLIF(EXCLUDED.nickname, ''), users.nickname),
                slack_id = COALESCE(EXCLUDED.slack_id, users.slack_id),
                avatar_url = COALESCE(EXCLUDED.avatar_url, users.avatar_url),
                updated_at = NOW()
            """,
            (user_id, name, nickname, slack_id, avatar_url),
        )
        conn.commit()
        cur.close()
    except Exception as e:
        if conn:
            conn.rollback()
        raise e


def nickname_for_slack(slack_id):
    if not slack_id:
        return None
    conn = get_db()
    if not conn:
        return None
    try:
        cur = conn.cursor()
        cur.execute("SELECT nickname FROM users WHERE slack_id = %s LIMIT 1", (slack_id,))
        row = cur.fetchone()
        cur.close()
        return row[0] if row else None
    except Exception:
        return None


def avatar_for_slack(slack_id):
    if not slack_id:
        return None
    conn = get_db()
    if not conn:
        return None
    try:
        cur = conn.cursor()
        cur.execute("SELECT avatar_url FROM users WHERE slack_id = %s LIMIT 1", (slack_id,))
        row = cur.fetchone()
        cur.close()
        return row[0] if row and row[0] else None
    except Exception:
        return None


def slack_and_avatar_for_user(user_id):
    if not user_id:
        return (None, None)
    conn = get_db()
    if not conn:
        return (None, None)
    try:
        cur = conn.cursor()
        cur.execute("SELECT slack_id, avatar_url FROM users WHERE id = %s LIMIT 1", (user_id,))
        row = cur.fetchone()
        cur.close()
        if not row:
            return (None, None)
        return (row[0], row[1] if row[1] else None)
    except Exception:
        return (None, None)


def save_avatar_for_slack(slack_id, avatar_url):
    if not slack_id or not avatar_url:
        return
    conn = get_db()
    if not conn:
        return
    try:
        cur = conn.cursor()
        cur.execute("UPDATE users SET avatar_url = %s, updated_at = NOW() WHERE slack_id = %s", (avatar_url, slack_id))
        conn.commit()
        cur.close()
    except Exception:
        if conn:
            conn.rollback()


def save_profile_for_slack(slack_id, nickname, avatar_url):
    if not slack_id:
        return
    conn = get_db()
    if not conn:
        return
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET nickname = COALESCE(NULLIF(%s, ''), nickname), avatar_url = COALESCE(%s, avatar_url), updated_at = NOW() WHERE slack_id = %s",
            (nickname, avatar_url, slack_id),
        )
        conn.commit()
        cur.close()
    except Exception:
        if conn:
            conn.rollback()


def save_user_from_slack(slack_id, display_name, avatar_url=None):
    if not slack_id or not display_name:
        return
    conn = get_db()
    if not conn:
        return
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO users (id, name, nickname, slack_id, avatar_url, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, nickname = COALESCE(EXCLUDED.nickname, users.nickname),
                slack_id = EXCLUDED.slack_id, avatar_url = COALESCE(EXCLUDED.avatar_url, users.avatar_url), updated_at = NOW()
            """,
            (slack_id, display_name, display_name, slack_id, avatar_url),
        )
        conn.commit()
        cur.close()
    except Exception:
        if conn:
            conn.rollback()


def approved_projects():
    conn = get_db()
    if not conn:
        return []
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, description, screenshot_path, submitted_by, submitted_by_slack_id, created_at FROM projects WHERE approved = TRUE ORDER BY created_at DESC"
    )
    rows = cur.fetchall()
    cur.close()
    return [
        {
            "id": r[0],
            "name": r[1],
            "description": r[2],
            "screenshot_path": r[3],
            "submitted_by": r[4],
            "submitted_by_slack_id": r[5] if len(r) > 5 else None,
            "created_at": r[6].isoformat() if len(r) > 6 and hasattr(r[6], "isoformat") else (str(r[6]) if len(r) > 6 else None),
        }
        for r in rows
    ]


def add_project(name, description, screenshot_path, submitted_by, submitted_by_user_id=None, submitted_by_slack_id=None):
    conn = get_db()
    if not conn:
        return None
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO projects (name, description, screenshot_path, submitted_by, submitted_by_user_id, submitted_by_slack_id, approved)
               VALUES (%s, %s, %s, %s, %s, %s, FALSE) RETURNING id""",
            (name, description, screenshot_path, submitted_by, submitted_by_user_id, submitted_by_slack_id),
        )
        pid = cur.fetchone()[0]
        conn.commit()
        cur.close()
        return pid
    except Exception:
        if conn:
            conn.rollback()
        return None


def add_dm_message(from_user_id, from_user_name, to_user_id, message):
    conn = get_db()
    if not conn:
        return
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO dm_messages (from_user_id, from_user_name, to_user_id, message) VALUES (%s, %s, %s, %s)",
            (from_user_id, from_user_name, to_user_id, message),
        )
        conn.commit()
        cur.close()
    except Exception:
        if conn:
            conn.rollback()


def messages_between(user_id_1, user_id_2):
    conn = get_db()
    if not conn:
        return []
    cur = conn.cursor()
    cur.execute(
        """SELECT from_user_id, from_user_name, message FROM dm_messages
           WHERE (from_user_id = %s AND to_user_id = %s) OR (from_user_id = %s AND to_user_id = %s)
           ORDER BY created_at""",
        (user_id_1, user_id_2, user_id_2, user_id_1),
    )
    rows = cur.fetchall()
    cur.close()
    return [{"from": r[1], "message": r[2]} for r in rows]


def mark_project_approved(project_id):
    conn = get_db()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("UPDATE projects SET approved = TRUE WHERE id = %s", (project_id,))
        n = cur.rowcount
        conn.commit()
        cur.close()
        return n > 0
    except Exception:
        if conn:
            conn.rollback()
        return False
