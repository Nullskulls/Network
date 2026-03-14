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