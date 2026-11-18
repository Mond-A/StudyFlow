"""Regression tests for legacy single-user databases."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts.migrate_iteration1 import migrate


def _legacy_database(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            PRAGMA foreign_keys = ON;
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
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                subject TEXT NOT NULL DEFAULT '综合',
                description TEXT NOT NULL DEFAULT '',
                due_date TEXT,
                estimated_minutes INTEGER NOT NULL DEFAULT 30,
                actual_minutes INTEGER NOT NULL DEFAULT 0,
                difficulty INTEGER NOT NULL DEFAULT 3,
                status TEXT NOT NULL DEFAULT 'pending',
                priority INTEGER NOT NULL DEFAULT 2,
                planned_date TEXT,
                planned_start TEXT,
                planned_minutes INTEGER,
                source TEXT NOT NULL DEFAULT 'manual',
                ai_meta TEXT,
                completed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            INSERT INTO users
                (username, display_name, avatar_color, daily_goal_minutes,
                 pomodoro_minutes, short_break_minutes, long_break_minutes,
                 timezone, created_at, updated_at)
            VALUES
                ('student', 'Legacy', '#2563eb', 120, 25, 5, 15,
                 'Asia/Shanghai', '2026-01-01T00:00:00+08:00',
                 '2026-01-01T00:00:00+08:00');
            INSERT INTO tasks
                (user_id, title, subject, estimated_minutes, status, source,
                 created_at, updated_at)
            VALUES
                (1, 'legacy-task', 'Math', 30, 'pending', 'manual',
                 '2026-01-01T00:00:00+08:00',
                 '2026-01-01T00:00:00+08:00');
            """
        )
        conn.commit()
    finally:
        conn.close()


def _counts(path: Path) -> tuple[int, int]:
    conn = sqlite3.connect(path)
    try:
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        tasks = conn.execute("SELECT COUNT(*) FROM tasks WHERE title = 'legacy-task'").fetchone()[0]
        return users, tasks
    finally:
        conn.close()


def test_init_schema_is_idempotent_for_legacy_database(app_factory, tmp_path):
    database = tmp_path / "legacy-init.db"
    _legacy_database(database)

    app = app_factory(DATABASE_PATH=str(database), UPLOAD_DIR=str(tmp_path / "uploads"))
    with app.app_context():
        from backend.db import query_one

        assert query_one(
            "SELECT COUNT(*) AS n FROM sqlite_master "
            "WHERE type = 'table' AND name = 'login_rate_limits'"
        )["n"] == 1
        assert query_one(
            "SELECT COUNT(*) AS n FROM auth_accounts"
        )["n"] == 0
    assert _counts(database) == (1, 1)

    # A second app startup must not overwrite the legacy rows or duplicate schema.
    app_factory(DATABASE_PATH=str(database), UPLOAD_DIR=str(tmp_path / "uploads"))
    assert _counts(database) == (1, 1)


def test_legacy_account_migration_creates_rate_table_and_is_idempotent(
    tmp_path, monkeypatch
):
    database = tmp_path / "legacy-migrate.db"
    uploads = tmp_path / "uploads"
    backups = tmp_path / "backups"
    _legacy_database(database)
    uploads.mkdir()
    monkeypatch.setenv(
        "STUDYFLOW_PASSWORD_HASH", "scrypt:32768:8:1$legacy$test"
    )

    first = migrate(database, uploads, backups, "legacy@example.invalid")
    assert first["account_action"] == "created_legacy_admin_account"
    assert _counts(database) == (1, 1)

    conn = sqlite3.connect(database)
    try:
        assert conn.execute("SELECT COUNT(*) FROM auth_accounts").fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM sqlite_master "
            "WHERE type = 'table' AND name = 'login_rate_limits'"
        ).fetchone()[0] == 1
    finally:
        conn.close()

    # Use a separate backup root so this test exercises migration idempotence
    # without depending on the snapshot timestamp's second-level uniqueness.
    second = migrate(database, uploads, tmp_path / "backups-second", "legacy@example.invalid")
    assert second["account_action"] == "existing_account_reused"
    assert _counts(database) == (1, 1)
