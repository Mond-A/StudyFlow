"""SQLite access helpers. One connection per Flask request context."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from flask import current_app, g, session

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
    """Create the legacy default user atomically; never overwrite an existing one."""
    timestamp = now_iso()
    conn.execute(
        """
        INSERT OR IGNORE INTO users
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
    row = conn.execute(
        "SELECT * FROM users WHERE username = ?", (DEFAULT_USERNAME,)
    ).fetchone()
    if row is None:
        raise RuntimeError("default user could not be created")
    return row


def get_current_user() -> sqlite3.Row:
    """Resolve the user exclusively from the authenticated session.

    The old implementation always returned the default user, which made every
    authenticated request share one data namespace. A missing/mismatched user
    is an authentication error, never a reason to fall back to user 1.
    """
    if "current_user" not in g:
        user_id = session.get("user_id")
        if not isinstance(user_id, int) or user_id <= 0:
            raise RuntimeError("Authenticated session has no valid user_id")
        row = query_one("SELECT * FROM users WHERE id = ?", (user_id,))
        if row is None:
            raise RuntimeError("Authenticated session references a missing user")
        g.current_user = row
    return g.current_user


def get_current_user_id() -> int:
    return int(get_current_user()["id"])


def _execute_schema(conn: sqlite3.Connection, text: str) -> None:
    """Execute schema statements inside the caller's explicit transaction."""
    statement = ""
    for line in text.splitlines(keepends=True):
        statement += line
        if sqlite3.complete_statement(statement):
            if statement.strip():
                conn.execute(statement)
            statement = ""
    if statement.strip():
        conn.execute(statement)


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    """Add a column to an existing v1.1.0 database without deleting data."""
    columns = {
        row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column in columns:
        return
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")
    except sqlite3.OperationalError as exc:
        if "duplicate column name" not in str(exc).lower():
            raise
        columns = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in columns:
            raise


def _parse_token_expiry(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        expires = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return expires


def _backfill_active_tokens(conn: sqlite3.Connection) -> None:
    """Normalize one active verification token per account under the init lock."""
    now = datetime.now().astimezone()
    accounts = conn.execute(
        "SELECT id, email_verified_at, active_verification_token_id FROM auth_accounts"
    ).fetchall()
    for account in accounts:
        account_id = int(account["id"])
        if account["email_verified_at"]:
            if account["active_verification_token_id"] is not None:
                conn.execute(
                    "UPDATE auth_accounts SET active_verification_token_id = NULL "
                    "WHERE id = ?",
                    (account_id,),
                )
            continue

        active_id = account["active_verification_token_id"]
        if active_id is not None:
            active = conn.execute(
                """
                SELECT id, used_at, expires_at
                FROM email_verification_tokens
                WHERE id = ? AND account_id = ?
                """,
                (active_id, account_id),
            ).fetchone()
            active_expiry = _parse_token_expiry(active["expires_at"]) if active else None
            if (
                active is not None
                and active["used_at"] is None
                and active_expiry is not None
                and active_expiry > now
            ):
                continue

        selected = None
        candidates = conn.execute(
            """
            SELECT id, used_at, expires_at
            FROM email_verification_tokens
            WHERE account_id = ? AND used_at IS NULL
            ORDER BY id DESC
            """,
            (account_id,),
        ).fetchall()
        for candidate in candidates:
            expires = _parse_token_expiry(candidate["expires_at"])
            if expires is not None and expires > now:
                selected = int(candidate["id"])
                break
        if selected != active_id:
            conn.execute(
                "UPDATE auth_accounts SET active_verification_token_id = ?, updated_at = ? "
                "WHERE id = ?",
                (selected, now_iso(), account_id),
            )


def init_schema(app) -> None:
    """Apply idempotent schema. Called on app startup and by the init script."""
    schema_path = Path(__file__).with_name("schema.sql")
    database_path = app.config["DATABASE_PATH"]
    if str(database_path) != ":memory:":
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    conn = connect_database(database_path)
    try:
        try:
            conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.DatabaseError:
            pass
        # One write lock covers schema, column migration, backfill and default
        # user creation. This is the multi-worker initialization serialization.
        conn.execute("BEGIN IMMEDIATE")
        _execute_schema(conn, schema_path.read_text(encoding="utf-8"))
        # v1.1.0 databases already have auth_accounts but not this pointer.
        _ensure_column(
            conn,
            "auth_accounts",
            "active_verification_token_id",
            "active_verification_token_id INTEGER",
        )
        _backfill_active_tokens(conn)
        ensure_default_user(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
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
