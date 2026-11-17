#!/usr/bin/env python3
"""Create and verify a consistent StudyFlow database + uploads snapshot.

The snapshot is written outside the repository's tracked paths (data/ is
ignored). The source database is opened read-only for verification; the
restore check uses a temporary copy, never the production database.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "data" / "studyflow.db"
DEFAULT_UPLOADS = PROJECT_ROOT / "data" / "uploads"
DEFAULT_BACKUP_ROOT = PROJECT_ROOT / "data" / "backups"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def table_counts(path: Path) -> dict[str, int]:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
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
    finally:
        conn.close()


def copy_uploads(source: Path, destination: Path) -> list[dict]:
    records = []
    if not source.exists():
        destination.mkdir(parents=True, exist_ok=True)
        return records
    for path in sorted(source.rglob("*")):
        if not path.is_file() or path.name == ".gitkeep":
            continue
        relative = path.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        records.append(
            {
                "relative_path": str(relative).replace("\\", "/"),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    destination.mkdir(parents=True, exist_ok=True)
    return records


def restore_check(backup_db: Path, expected_counts: dict[str, int], uploads: list[dict], uploads_dir: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="studyflow-restore-check-") as temp:
        temp_root = Path(temp)
        restored_db = temp_root / "restored.db"
        shutil.copy2(backup_db, restored_db)
        conn = sqlite3.connect(restored_db)
        try:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            restored_counts = {
                name: conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
                for name in expected_counts
            }
        finally:
            conn.close()

        restored_uploads = temp_root / "uploads"
        for record in uploads:
            relative = Path(record["relative_path"])
            source = uploads_dir / relative
            target = restored_uploads / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            if sha256_file(target) != record["sha256"]:
                raise RuntimeError(f"Upload restore hash mismatch: {relative}")

    if integrity != "ok":
        raise RuntimeError(f"Restored database integrity check failed: {integrity}")
    if restored_counts != expected_counts:
        raise RuntimeError(
            f"Restored database table counts do not match: {restored_counts} != {expected_counts}"
        )
    return {
        "integrity_check": integrity,
        "table_counts_match": True,
        "uploads_restored": len(uploads),
        "restore_verified": True,
    }


def create_snapshot(
    database: Path,
    uploads: Path,
    backup_root: Path,
    label: str = "manual",
) -> dict:
    database = database.expanduser().resolve()
    uploads = uploads.expanduser().resolve()
    backup_root = backup_root.expanduser().resolve()
    if not database.is_file():
        raise FileNotFoundError(f"Database not found: {database}")
    backup_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_label = "".join(char if char.isalnum() or char in "-_" else "-" for char in label)
    destination = backup_root / f"{safe_label}-{stamp}"
    destination.mkdir(parents=True, exist_ok=False)
    backup_db = destination / "studyflow.db"
    backup_uploads = destination / "uploads"
    backup_uploads.mkdir()

    source = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    target = sqlite3.connect(backup_db)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()

    # Open the backup independently before doing anything else with it.
    check = sqlite3.connect(f"file:{backup_db}?mode=ro", uri=True)
    try:
        integrity = check.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        check.close()
    if integrity != "ok":
        raise RuntimeError(f"Backup database integrity check failed: {integrity}")

    source_counts = table_counts(database)
    backup_counts = table_counts(backup_db)
    if source_counts != backup_counts:
        raise RuntimeError(
            f"Backup table counts do not match source: {backup_counts} != {source_counts}"
        )

    upload_records = copy_uploads(uploads, backup_uploads)
    restore = restore_check(backup_db, backup_counts, upload_records, backup_uploads)

    git_commit = None
    try:
        git_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        pass

    manifest = {
        "format": "studyflow-backup-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "label": safe_label,
        "source_database": str(database),
        "backup_database": str(backup_db),
        "backup_uploads": str(backup_uploads),
        "git_commit": git_commit,
        "database_size": backup_db.stat().st_size,
        "database_sha256": sha256_file(backup_db),
        "table_counts": backup_counts,
        "upload_count": len(upload_records),
        "uploads": upload_records,
        "integrity_check": integrity,
        "restore": restore,
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {"destination": str(destination), **manifest}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default=str(DEFAULT_DB))
    parser.add_argument("--uploads", default=str(DEFAULT_UPLOADS))
    parser.add_argument("--backup-root", default=str(DEFAULT_BACKUP_ROOT))
    parser.add_argument("--label", default="manual")
    args = parser.parse_args(argv)
    try:
        report = create_snapshot(
            Path(args.database), Path(args.uploads), Path(args.backup_root), args.label
        )
    except Exception as error:
        print(f"[error] backup did not complete: {error}", flush=True)
        return 1
    print(f"Backup: {report['destination']}")
    print(f"Database SHA256: {report['database_sha256']}")
    print(f"Tables: {report['table_counts']}")
    print(f"Uploads: {report['upload_count']}")
    print(f"Restore check: {report['restore']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
