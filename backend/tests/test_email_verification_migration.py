"""Independent v1.1.0 -> v1.1.1 schema and active-token migration tests."""

from __future__ import annotations

import hashlib
import multiprocessing
import sqlite3
import threading
from datetime import datetime, timedelta

import pytest
from flask import Flask

import backend.db as db_module
from backend.accounts import verify_email_token
from backend.db import connect_database, init_schema
from backend.utils.exceptions import APIError

OLD_SCHEMA = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    email TEXT,
    avatar_color TEXT NOT NULL DEFAULT '#2563eb',
    daily_goal_minutes INTEGER NOT NULL DEFAULT 120,
    pomodoro_minutes INTEGER NOT NULL DEFAULT 25,
    short_break_minutes INTEGER NOT NULL DEFAULT 5,
    long_break_minutes INTEGER NOT NULL DEFAULT 15,
    timezone TEXT NOT NULL DEFAULT 'Asia/Shanghai',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE auth_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    email TEXT NOT NULL COLLATE NOCASE UNIQUE,
    password_hash TEXT NOT NULL,
    email_verified_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE email_verification_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    used_at TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE legacy_probe (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def _make_app(database):
    app = Flask(__name__)
    app.config.update(
        DATABASE_PATH=str(database),
        TIMEZONE="Asia/Shanghai",
        EMAIL_VERIFICATION_HOURS=24,
        TESTING=True,
    )
    return app


def _iso(hours: int = 24) -> str:
    return (datetime.now().astimezone() + timedelta(hours=hours)).isoformat(
        timespec="seconds"
    )


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _create_old_database(path, *, verified=False):
    conn = connect_database(path)
    try:
        conn.executescript(OLD_SCHEMA)
        stamp = _iso(0)
        cursor = conn.execute(
            """
            INSERT INTO users
                (username, display_name, email, avatar_color, daily_goal_minutes,
                 pomodoro_minutes, short_break_minutes, long_break_minutes,
                 timezone, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("olduser", "Old", "old@example.test", "#2563eb", 120, 25, 5, 15,
             "Asia/Shanghai", stamp, stamp),
        )
        user_id = int(cursor.lastrowid)
        cursor = conn.execute(
            """
            INSERT INTO auth_accounts
                (user_id, email, password_hash, email_verified_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, "old@example.test", "scrypt:old", stamp if verified else None,
             stamp, stamp),
        )
        account_id = int(cursor.lastrowid)
        conn.execute(
            "INSERT INTO legacy_probe (user_id, title, created_at, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (user_id, "preserve-me", stamp, stamp),
        )
        conn.commit()
        return conn, account_id
    except Exception:
        conn.close()
        raise


def _add_token(conn, account_id, token, *, expires_hours=24, used=False):
    conn.execute(
        """
        INSERT INTO email_verification_tokens
            (account_id, token_hash, expires_at, used_at, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (account_id, _hash(token), _iso(expires_hours), _iso(0) if used else None, _iso(0)),
    )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _init(database):
    app = _make_app(database)
    with app.app_context():
        init_schema(app)
    return app


def _verify(app, token):
    with app.app_context():
        return verify_email_token(token)


def _schema_column(database):
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    try:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(auth_accounts)").fetchall()
        }
        account = conn.execute(
            "SELECT active_verification_token_id FROM auth_accounts WHERE id = 1"
        ).fetchone()
        counts = {
            "users": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "accounts": conn.execute("SELECT COUNT(*) FROM auth_accounts").fetchone()[0],
            "probe": conn.execute("SELECT COUNT(*) FROM legacy_probe").fetchone()[0],
        }
    finally:
        conn.close()
    return columns, account[0], counts


def test_old_database_backfills_latest_valid_unused_token(tmp_path):
    database = tmp_path / "old-one.sqlite"
    conn, account_id = _create_old_database(database)
    try:
        _add_token(conn, account_id, "valid-old")
        conn.commit()
    finally:
        conn.close()

    app = _init(database)
    columns, active, _counts = _schema_column(database)
    assert "active_verification_token_id" in columns
    assert active is not None
    _verify(app, "valid-old")


def test_multiple_old_tokens_only_latest_is_active(tmp_path):
    database = tmp_path / "old-multiple.sqlite"
    conn, account_id = _create_old_database(database)
    try:
        _add_token(conn, account_id, "older-valid")
        latest_id = _add_token(conn, account_id, "latest-valid")
        conn.commit()
    finally:
        conn.close()

    app = _init(database)
    _columns, active, _counts = _schema_column(database)
    assert active == latest_id
    with pytest.raises(APIError, match="无效或已过期"):
        _verify(app, "older-valid")
    _verify(app, "latest-valid")


def test_expired_and_used_tokens_do_not_become_active(tmp_path):
    database = tmp_path / "old-none-valid.sqlite"
    conn, account_id = _create_old_database(database)
    try:
        _add_token(conn, account_id, "expired-only", expires_hours=-1)
        _add_token(conn, account_id, "used-only", used=True)
        conn.commit()
    finally:
        conn.close()

    app = _init(database)
    _columns, active, _counts = _schema_column(database)
    assert active is None
    with pytest.raises(APIError):
        _verify(app, "expired-only")
    with pytest.raises(APIError):
        _verify(app, "used-only")


def test_verified_account_is_not_given_active_token(tmp_path):
    database = tmp_path / "old-verified.sqlite"
    conn, account_id = _create_old_database(database, verified=True)
    try:
        _add_token(conn, account_id, "already-verified")
        conn.commit()
    finally:
        conn.close()

    app = _init(database)
    _columns, active, _counts = _schema_column(database)
    assert active is None
    with pytest.raises(APIError):
        _verify(app, "already-verified")


def test_stale_active_pointer_is_repaired_to_latest_valid_token(tmp_path):
    database = tmp_path / "old-stale.sqlite"
    conn, account_id = _create_old_database(database)
    try:
        expired_id = _add_token(conn, account_id, "expired-pointer", expires_hours=-1)
        valid_id = _add_token(conn, account_id, "valid-pointer")
        conn.commit()
    finally:
        conn.close()

    app = _init(database)
    conn = sqlite3.connect(database)
    try:
        conn.execute(
            "UPDATE auth_accounts SET active_verification_token_id = ? WHERE id = ?",
            (expired_id, account_id),
        )
        conn.commit()
    finally:
        conn.close()

    _init(database)
    _columns, active, _counts = _schema_column(database)
    assert active == valid_id
    _verify(app, "valid-pointer")


def test_migration_failure_rolls_back_and_can_retry(tmp_path, monkeypatch):
    database = tmp_path / "retry.sqlite"
    conn, account_id = _create_old_database(database)
    try:
        _add_token(conn, account_id, "retry-token")
        conn.commit()
    finally:
        conn.close()

    app = _make_app(database)
    original = db_module._backfill_active_tokens

    def fail(conn):
        raise RuntimeError("simulated migration failure")

    monkeypatch.setattr(db_module, "_backfill_active_tokens", fail)
    with app.app_context():
        with pytest.raises(RuntimeError, match="simulated"):
            init_schema(app)

    monkeypatch.setattr(db_module, "_backfill_active_tokens", original)
    with app.app_context():
        init_schema(app)

    columns, active, counts = _schema_column(database)
    assert "active_verification_token_id" in columns
    assert active is not None
    assert counts["users"] == 2
    assert counts["accounts"] == 1
    assert counts["probe"] == 1


def test_concurrent_thread_initialization_is_idempotent(tmp_path):
    failures = []
    for round_number in range(12):
        database = tmp_path / f"thread-{round_number}.sqlite"
        conn, account_id = _create_old_database(database)
        try:
            _add_token(conn, account_id, f"thread-token-{round_number}")
            conn.commit()
        finally:
            conn.close()
        app = _make_app(database)
        barrier = threading.Barrier(2)

        def worker():
            try:
                with app.app_context():
                    barrier.wait(timeout=5)
                    init_schema(app)
            except Exception as exc:  # noqa: BLE001
                failures.append((round_number, type(exc).__name__, str(exc)))

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)
        columns, active, counts = _schema_column(database)
        assert "active_verification_token_id" in columns
        assert active is not None
        assert counts["users"] == 2  # olduser + default student
        assert counts["accounts"] == 1
        assert counts["probe"] == 1
    assert failures == []


def _process_worker(database, queue):
    try:
        app = _make_app(database)
        with app.app_context():
            init_schema(app)
        queue.put("ok")
    except Exception as exc:  # noqa: BLE001
        queue.put(f"{type(exc).__name__}: {exc}")


def test_concurrent_process_initialization(tmp_path):
    database = tmp_path / "process.sqlite"
    conn, account_id = _create_old_database(database)
    try:
        _add_token(conn, account_id, "process-token")
        conn.commit()
    finally:
        conn.close()

    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    processes = [
        context.Process(target=_process_worker, args=(str(database), queue))
        for _ in range(2)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(20)
    results = [queue.get(timeout=5) for _ in processes]
    assert results == ["ok", "ok"]
    assert all(process.exitcode == 0 for process in processes)
    columns, active, counts = _schema_column(database)
    assert "active_verification_token_id" in columns
    assert active is not None
    assert counts["users"] == 2
    assert counts["accounts"] == 1
    assert counts["probe"] == 1
