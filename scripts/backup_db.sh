#!/usr/bin/env bash
# Online SQLite + uploads backup for a running StudyFlow instance.
set -Eeuo pipefail
umask 077

APP_DIR="${STUDYFLOW_APP_DIR:-/opt/studyflow}"
BACKUP_DIR="${STUDYFLOW_BACKUP_DIR:-/var/backups/studyflow}"
DB_PATH="${STUDYFLOW_DB_PATH:-$APP_DIR/data/studyflow.db}"
UPLOADS_DIR="${STUDYFLOW_UPLOADS_DIR:-$APP_DIR/data/uploads}"

if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "sqlite3 is required (apt install sqlite3)." >&2
  exit 1
fi
if [ ! -f "$DB_PATH" ]; then
  echo "Database not found: $DB_PATH" >&2
  exit 1
fi

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$BACKUP_DIR"
db_backup="$BACKUP_DIR/studyflow-db-$stamp.sqlite"
tmp_db="$BACKUP_DIR/.studyflow-db-$stamp.tmp"

# SQLite's online backup API creates a consistent copy while Gunicorn is live.
sqlite3 "$DB_PATH" ".backup '$tmp_db'"
mv "$tmp_db" "$db_backup"
chmod 600 "$db_backup"

if [ -d "$UPLOADS_DIR" ]; then
  uploads_backup="$BACKUP_DIR/studyflow-uploads-$stamp.tar.gz"
  tar -C "$(dirname "$UPLOADS_DIR")" -czf "$uploads_backup" "$(basename "$UPLOADS_DIR")"
  chmod 600 "$uploads_backup"
  echo "Uploads: $uploads_backup"
fi

echo "Database: $db_backup"
sha256sum "$db_backup"
if [ -n "${uploads_backup:-}" ] && [ -f "$uploads_backup" ]; then
  sha256sum "$uploads_backup"
fi
echo "Backup complete. Copy these files off the Orange Pi."
