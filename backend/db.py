"""SQLite access helpers. One connection per Flask request context."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from flask import current_app, g

from .utils.timeutils import now_iso

DEFAULT_USERNAME = "student"


def connect_database(path: str | Path) -> sqlite3.Connection:
    path = str(path)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = connect_database(current_app.config["DATABASE_PATH"])
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query_all(sql: str, params=()) -> list[sqlite3.Row]:
    return get_db().execute(sql, params).fetchall()


def query_one(sql: str, params=()) -> sqlite3.Row | None:
    return get_db().execute(sql, params).fetchone()


def execute(sql: str, params=(), *, commit: bool = True):
    db = get_db()
    cursor = db.execute(sql, params)
    if commit:
        db.commit()
    return cursor


@contextmanager
def transaction():
    db = get_db()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise


def ensure_default_user(conn: sqlite3.Connection) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM users WHERE username = ?", (DEFAULT_USERNAME,)
    ).fetchone()
    if row is not None:
        return row
    timestamp = now_iso()
    cursor = conn.execute(
        """
        INSERT INTO users
            (username, display_name, avatar_color, daily_goal_minutes,
             pomodoro_minutes, short_break_minutes, long_break_minutes,
             timezone, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            DEFAULT_USERNAME,
            "同学",
            "#2563eb",
            120,
            25,
            5,
            15,
            current_app.config.get("TIMEZONE", "Asia/Shanghai"),
            timestamp,
            timestamp,
        ),
    )
    conn.commit()
    return conn.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()


def get_current_user() -> sqlite3.Row:
    if "current_user" not in g:
        g.current_user = ensure_default_user(get_db())
    return g.current_user


def get_current_user_id() -> int:
    return int(get_current_user()["id"])


def init_schema(app) -> None:
    """Apply idempotent schema. Called on app startup and by the init script."""
    schema_path = Path(__file__).with_name("schema.sql")
    database_path = app.config["DATABASE_PATH"]
    if str(database_path) != ":memory:":
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    conn = connect_database(database_path)
    try:
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        try:
            conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.DatabaseError:
            pass
        ensure_default_user(conn)
        conn.commit()
    finally:
        conn.close()


def get_meta(key: str, default: str | None = None) -> str | None:
    row = query_one("SELECT value FROM app_meta WHERE key = ?", (key,))
    return row["value"] if row else default


def set_meta(key: str, value: str, *, commit: bool = True) -> None:
    execute(
        """
        INSERT INTO app_meta (key, value, updated_at) VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """,
        (key, value, now_iso()),
        commit=commit,
    )
