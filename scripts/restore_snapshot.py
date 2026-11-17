#!/usr/bin/env python3
"""Explicit, operator-driven restore from a verified StudyFlow snapshot.

There is intentionally no default target and this script is never called by
the migration failure path. Before replacing a database it makes and verifies
a fresh safety snapshot of the current target and prints both paths.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_UPLOADS = PROJECT_ROOT / "data" / "uploads"
DEFAULT_BACKUP_ROOT = PROJECT_ROOT / "data" / "backups"
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.backup_snapshot import create_snapshot, sha256_file, table_counts  # noqa: E402


def restore(
    backup_db: Path,
    target_db: Path,
    uploads: Path,
    backup_root: Path,
) -> dict:
    backup_db = backup_db.expanduser().resolve()
    target_db = target_db.expanduser().resolve()
    uploads = uploads.expanduser().resolve()
    backup_root = backup_root.expanduser().resolve()
    if not backup_db.is_file():
        raise FileNotFoundError(f"Backup database not found: {backup_db}")
    if not target_db.is_file():
        raise FileNotFoundError(f"Explicit target database not found: {target_db}")
    if backup_db == target_db:
        raise ValueError("Backup and restore target must be different files")
    backup_conn = sqlite3.connect(f"file:{backup_db}?mode=ro", uri=True)
    try:
        if backup_conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Backup database failed integrity_check")
    finally:
        backup_conn.close()

    safety = create_snapshot(
        target_db,
        uploads,
        backup_root,
        label="pre-manual-restore",
    )
    target_counts = table_counts(target_db)
    backup_counts = table_counts(backup_db)
    if target_counts != backup_counts:
        # Different table sets are expected across schema versions; record
        # both, but do not block an explicit restore solely for that reason.
        print("Warning: current target and backup table counts differ.")
    shutil.copy2(backup_db, target_db)
    check = sqlite3.connect(f"file:{target_db}?mode=ro", uri=True)
    try:
        integrity = check.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        check.close()
    if integrity != "ok":
        raise RuntimeError(
            f"Restored target failed integrity_check; safety snapshot: {safety['destination']}"
        )
    return {
        "target": str(target_db),
        "source": str(backup_db),
        "target_sha256": sha256_file(target_db),
        "backup_sha256": sha256_file(backup_db),
        "safety_snapshot": safety["destination"],
        "integrity_check": integrity,
        "target_counts_before": target_counts,
        "backup_counts": backup_counts,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup-db", required=True, help="verified source snapshot DB")
    parser.add_argument("--database", required=True, help="explicit target DB to overwrite")
    parser.add_argument("--uploads", default=str(DEFAULT_UPLOADS))
    parser.add_argument("--backup-root", default=str(DEFAULT_BACKUP_ROOT))
    args = parser.parse_args(argv)
    try:
        report = restore(
            Path(args.backup_db),
            Path(args.database),
            Path(args.uploads),
            Path(args.backup_root),
        )
    except Exception as error:
        print(f"[error] restore did not complete: {error}", file=sys.stderr)
        return 1
    print("Restore complete. Review the target and safety snapshot explicitly:")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
