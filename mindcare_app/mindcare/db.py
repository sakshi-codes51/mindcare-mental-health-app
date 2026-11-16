"""SQLite access using the standard library (no ORM required)."""
import sqlite3
from datetime import datetime, timezone

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    user_type     TEXT NOT NULL DEFAULT 'other',
    age_group     TEXT,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS screenings (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at       TEXT NOT NULL,
    answers          TEXT NOT NULL,
    anxiety_score    INTEGER NOT NULL,
    depression_score INTEGER NOT NULL,
    total_score      INTEGER NOT NULL,
    severity_band    TEXT NOT NULL,
    category         TEXT NOT NULL,
    safety_flag      INTEGER NOT NULL DEFAULT 0,
    context_flags    TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_screenings_user ON screenings(user_id, created_at);

CREATE TABLE IF NOT EXISTS mood_entries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at      TEXT NOT NULL,
    entry_date      TEXT NOT NULL,
    mood            INTEGER NOT NULL,
    sleep_hours     REAL,
    stress          INTEGER,
    note            TEXT NOT NULL DEFAULT '',
    primary_emotion TEXT,
    sentiment       REAL,
    distress        TEXT
);
CREATE INDEX IF NOT EXISTS idx_mood_user_date ON mood_entries(user_id, entry_date);

CREATE TABLE IF NOT EXISTS analyses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at      TEXT NOT NULL,
    text            TEXT NOT NULL,
    primary_emotion TEXT NOT NULL,
    sentiment       REAL NOT NULL,
    distribution    TEXT NOT NULL,
    evidence        TEXT NOT NULL DEFAULT '[]',
    distress        TEXT NOT NULL,
    crisis          INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_analyses_user ON analyses(user_id, created_at);

CREATE TABLE IF NOT EXISTS chat_messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role       TEXT NOT NULL CHECK (role IN ('user', 'bot')),
    content    TEXT NOT NULL,
    emotion    TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat_user ON chat_messages(user_id, id);

CREATE TABLE IF NOT EXISTS login_attempts (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    ts    REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attempts_email ON login_attempts(email, ts);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        conn = sqlite3.connect(current_app.config["DATABASE"])
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        g.db = conn
    return g.db


def close_db(exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db():
    conn = get_db()
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(SCHEMA)
    conn.commit()


def init_app(app):
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()
