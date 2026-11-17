#!/usr/bin/env python3
"""Idempotent Iteration 1 schema/account migration.

This script never changes the user_id of existing business rows. It creates
the new account/verification/upload/import/idempotency tables and links the
existing default profile to a legacy verified account.

The admin email is supplied by the operator. The initial password hash is read
from STUDYFLOW_PASSWORD_HASH (never a command-line value or source constant).

Before any schema change, a consistent database + uploads snapshot is created
and restore-checked by scripts/backup_snapshot.py.

Usage:
    STUDYFLOW_PASSWORD_HASH='...' python scripts/migrate_iteration1.py \
        --admin-email admin@example.com
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "data" / "studyflow.db"
DEFAULT_UPLOADS = PROJECT_ROOT / "data" / "uploads"
DEFAULT_BACKUP_ROOT = PROJECT_ROOT / "data" / "backups"
MIGRATION_VERSION = "iteration1_accounts_v1"

SCHEMA_PATH = PROJECT_ROOT / "backend" / "schema.sql"
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv  # noqa: E402

from scripts.backup_snapshot import create_snapshot  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")


def _now() -> str:
    from datetime import datetime

    return datetime.now().astimezone().isoformat(timespec="seconds")


def _valid_email(value: str) -> str:
    email = str(value or "").strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError("admin email is not a valid email address")
    return email


def _password_hash() -> str:
    value = os.getenv("STUDYFLOW_PASSWORD_HASH", "").strip()
    if not value or value.count("$") < 2:
        raise RuntimeError(
            "STUDYFLOW_PASSWORD_HASH is missing or invalid. "
            "Set the existing admin password hash in the environment before migration."
        )
    return value


def _admin_user(conn: sqlite3.Connection) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM users WHERE username = 'student' ORDER BY id LIMIT 1"
    ).fetchone()
    if row is None:
        row = conn.execute("SELECT * FROM users ORDER BY id LIMIT 1").fetchone()
    if row is not None:
        return row
    timestamp = _now()
    cursor = conn.execute(
        """
        INSERT INTO users
            (username, display_name, avatar_color, daily_goal_minutes,
             pomodoro_minutes, short_break_minutes, long_break_minutes,
             timezone, created_at, updated_at)
        VALUES (?, ?, ?, 120, 25, 5, 15, 'Asia/Shanghai', ?, ?)
        """,
        ("admin", "管理员", "#2563eb", timestamp, timestamp),
    )
    return conn.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()


def _ensure_account(
    conn: sqlite3.Connection,
    user_id: int,
    email: str,
    password_hash: str,
) -> tuple[int, str]:
    account = conn.execute(
        "SELECT * FROM auth_accounts WHERE user_id = ?", (user_id,)
    ).fetchone()
    if account is not None:
        if account["email"].lower() != email:
            return int(account["id"]), "existing_account_email_kept"
        if not account["email_verified_at"]:
            conn.execute(
                "UPDATE auth_accounts SET email_verified_at = ?, updated_at = ? WHERE id = ?",
                (_now(), _now(), account["id"]),
            )
        return int(account["id"]), "existing_account_reused"
    conflict = conn.execute(
        "SELECT id FROM auth_accounts WHERE lower(email) = ?", (email,)
    ).fetchone()
    if conflict is not None:
        raise RuntimeError("admin email is already linked to another account")
    timestamp = _now()
    cursor = conn.execute(
        """
        INSERT INTO auth_accounts
            (user_id, email, password_hash, email_verified_at, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, email, password_hash, timestamp, timestamp, timestamp),
    )
    return int(cursor.lastrowid), "created_legacy_admin_account"


def _upload_rows(conn: sqlite3.Connection, user_id: int, uploads_dir: Path) -> dict:
    if not uploads_dir.exists():
        return {"registered": 0, "skipped": 0, "missing_dir": True}
    registered = 0
    skipped = 0
    timestamp = _now()
    for path in sorted(uploads_dir.rglob("*")):
        if not path.is_file() or path.name in {".gitkeep", ".DS_Store"}:
            continue
        relative = str(path.relative_to(uploads_dir)).replace("\\", "/")
        existing = conn.execute(
            "SELECT id, user_id FROM uploads WHERE stored_filename = ?", (relative,)
        ).fetchone()
        if existing is not None:
            skipped += 1
            continue
        import mimetypes

        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        conn.execute(
            """
            INSERT INTO uploads
                (user_id, stored_filename, original_name, content_type, size_bytes, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, relative, path.name, mime, path.stat().st_size, timestamp),
        )
        registered += 1
    return {"registered": registered, "skipped": skipped, "missing_dir": False}


def _counts(conn: sqlite3.Connection) -> dict[str, int]:
    names = [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    return {
        name: conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        for name in names
    }


def migrate(
    database: Path,
    uploads_dir: Path,
    backup_root: Path,
    admin_email: str,
) -> dict:
    database = database.expanduser().resolve()
    uploads_dir = uploads_dir.expanduser().resolve()
    backup_root = backup_root.expanduser().resolve()
    email = _valid_email(admin_email)
    if not database.is_file():
        raise FileNotFoundError(f"Database not found: {database}")

    # Validate credentials before touching even the backup/schema. If an
    # account already exists, the hash is only needed for account creation.
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    try:
        already_has_account = conn.execute("SELECT COUNT(*) FROM auth_accounts").fetchone()[0] if conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='auth_accounts'"
        ).fetchone() else 0
    finally:
        conn.close()
    password_hash = "" if already_has_account else _password_hash()

    before = create_snapshot(
        database,
        uploads_dir,
        backup_root,
        label="iteration1-pre-migration",
    )
    backup_path = before["destination"]

    before_counts = before["table_counts"]
    # isolation_level=None lets us own the transaction boundary. DDL and data
    # must commit together; executescript() is deliberately not used because
    # it can commit before unrelated data operations fail.
    conn = sqlite3.connect(database, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        conn.execute("BEGIN IMMEDIATE")
        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        for raw_statement in schema_sql.split(";"):
            statement = raw_statement.strip()
            if statement:
                conn.execute(statement)

        user = _admin_user(conn)
        account_id, account_action = _ensure_account(
            conn, int(user["id"]), email, password_hash
        )
        upload_result = _upload_rows(conn, int(user["id"]), uploads_dir)
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (MIGRATION_VERSION, _now()),
        )
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = conn.execute("PRAGMA foreign_key_check").fetchall()
        if integrity != "ok":
            raise RuntimeError(f"Database integrity check failed: {integrity}")
        if foreign_keys:
            raise RuntimeError(f"Foreign-key check failed: {foreign_keys[:3]}")
        after_counts = _counts(conn)
        data_counts = {
            key: after_counts.get(key, 0)
            for key in before_counts
            if key
            not in {
                "auth_accounts",
                "email_verification_tokens",
                "uploads",
                "guest_import_batches",
                "guest_import_items",
                "idempotency_keys",
                "schema_migrations",
            }
        }
        if any(before_counts.get(key, 0) != value for key, value in data_counts.items()):
            raise RuntimeError("Business table counts changed during migration; rolling back.")
        conn.commit()
    except Exception as error:
        try:
            conn.rollback()
        except sqlite3.Error as rollback_error:
            raise RuntimeError(
                "Migration failed and SQLite rollback could not be confirmed. "
                f"The database was NOT overwritten. Preserve the site and use the "
                f"verified backup at {backup_path} only through an explicit manual "
                "restore with a fresh safety backup."
            ) from rollback_error
        raise error
    finally:
        conn.close()

    report = {
        "migration": MIGRATION_VERSION,
        "admin_user_id": int(user["id"]),
        "account_id": account_id,
        "account_action": account_action,
        "admin_email": email,
        "backup": backup_path,
        "backup_database_sha256": before["database_sha256"],
        "before_counts": before_counts,
        "after_counts": after_counts,
        "business_counts_unchanged": True,
        "uploads": upload_result,
        "integrity_check": integrity,
        "restore_verified": before["restore"]["restore_verified"],
    }
    report_path = Path(backup_path) / "migration-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["report_path"] = str(report_path)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admin-email", required=True)
    parser.add_argument("--database", default=str(DEFAULT_DB))
    parser.add_argument("--uploads", default=str(DEFAULT_UPLOADS))
    parser.add_argument("--backup-root", default=str(DEFAULT_BACKUP_ROOT))
    args = parser.parse_args(argv)
    try:
        report = migrate(
            Path(args.database),
            Path(args.uploads),
            Path(args.backup_root),
            args.admin_email,
        )
    except Exception as error:
        print(f"[error] migration did not complete: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
