-- StudyFlow SQLite schema (MVP - all business rows are scoped by user_id)
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    username            TEXT NOT NULL UNIQUE,
    display_name        TEXT NOT NULL,
    email               TEXT,
    avatar_color        TEXT NOT NULL DEFAULT '#2563eb',
    daily_goal_minutes  INTEGER NOT NULL DEFAULT 120 CHECK (daily_goal_minutes BETWEEN 15 AND 1440),
    pomodoro_minutes    INTEGER NOT NULL DEFAULT 25 CHECK (pomodoro_minutes BETWEEN 1 AND 120),
    short_break_minutes INTEGER NOT NULL DEFAULT 5 CHECK (short_break_minutes BETWEEN 1 AND 60),
    long_break_minutes  INTEGER NOT NULL DEFAULT 15 CHECK (long_break_minutes BETWEEN 1 AND 120),
    timezone            TEXT NOT NULL DEFAULT 'Asia/Shanghai',
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title             TEXT NOT NULL,
    subject           TEXT NOT NULL DEFAULT '综合',
    description       TEXT NOT NULL DEFAULT '',
    due_date          TEXT,
    estimated_minutes INTEGER NOT NULL DEFAULT 30 CHECK (estimated_minutes BETWEEN 1 AND 1440),
    actual_minutes    INTEGER NOT NULL DEFAULT 0 CHECK (actual_minutes >= 0),
    difficulty        INTEGER NOT NULL DEFAULT 3 CHECK (difficulty BETWEEN 1 AND 5),
    status            TEXT NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending', 'in_progress', 'completed')),
    priority          INTEGER NOT NULL DEFAULT 2 CHECK (priority BETWEEN 1 AND 3),
    planned_date      TEXT,
    planned_start     TEXT,
    planned_minutes   INTEGER CHECK (planned_minutes IS NULL OR planned_minutes > 0),
    source            TEXT NOT NULL DEFAULT 'manual'
                      CHECK (source IN ('manual', 'ai', 'import')),
    ai_meta           TEXT,
    completed_at      TEXT,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS grades (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject     TEXT NOT NULL,
    exam_name   TEXT NOT NULL,
    score       REAL NOT NULL CHECK (score >= 0),
    max_score   REAL NOT NULL DEFAULT 100 CHECK (max_score > 0 AND score <= max_score),
    exam_date   TEXT NOT NULL,
    notes       TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notes (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id               INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title                 TEXT NOT NULL,
    subject               TEXT NOT NULL DEFAULT '综合',
    content_markdown      TEXT NOT NULL DEFAULT '',
    source_image          TEXT,
    audit_report          TEXT,
    knowledge_graph       TEXT,
    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS study_sessions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task_id          INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    subject          TEXT NOT NULL DEFAULT '综合',
    duration_minutes INTEGER NOT NULL CHECK (duration_minutes BETWEEN 1 AND 1440),
    session_type     TEXT NOT NULL DEFAULT 'pomodoro'
                     CHECK (session_type IN ('pomodoro', 'free', 'manual', 'task')),
    started_at       TEXT NOT NULL,
    ended_at         TEXT,
    note             TEXT NOT NULL DEFAULT '',
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS achievements (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code        TEXT NOT NULL,
    title       TEXT NOT NULL,
    description TEXT NOT NULL,
    icon        TEXT NOT NULL DEFAULT 'award',
    unlocked_at TEXT NOT NULL,
    UNIQUE (user_id, code)
);

CREATE TABLE IF NOT EXISTS error_records (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject          TEXT NOT NULL,
    question         TEXT NOT NULL,
    student_answer   TEXT NOT NULL DEFAULT '',
    correct_answer   TEXT NOT NULL DEFAULT '',
    analysis         TEXT NOT NULL DEFAULT '',
    knowledge_points TEXT NOT NULL DEFAULT '[]',
    mastery          TEXT NOT NULL DEFAULT 'new'
                     CHECK (mastery IN ('new', 'reviewing', 'mastered')),
    source           TEXT NOT NULL DEFAULT 'manual',
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS flashcards (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    note_id          INTEGER REFERENCES notes(id) ON DELETE SET NULL,
    front            TEXT NOT NULL,
    back             TEXT NOT NULL,
    subject          TEXT NOT NULL DEFAULT '综合',
    mastery_level    INTEGER NOT NULL DEFAULT 0 CHECK (mastery_level BETWEEN 0 AND 5),
    review_count     INTEGER NOT NULL DEFAULT 0,
    next_review_date TEXT,
    last_reviewed_at TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

-- Records created by the optional demo seed, so users can remove only demo data.
CREATE TABLE IF NOT EXISTS demo_records (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    table_name  TEXT NOT NULL,
    record_id   INTEGER NOT NULL,
    created_at  TEXT NOT NULL,
    UNIQUE (table_name, record_id)
);

CREATE TABLE IF NOT EXISTS app_meta (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Iteration 1: formal email accounts are linked one-to-one to a profile row.
-- The profile email in users.email is not used as the authentication identifier.
CREATE TABLE IF NOT EXISTS auth_accounts (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    email             TEXT NOT NULL COLLATE NOCASE UNIQUE,
    password_hash     TEXT NOT NULL,
    email_verified_at TEXT,
    active_verification_token_id INTEGER,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS email_verification_tokens (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id  INTEGER NOT NULL REFERENCES auth_accounts(id) ON DELETE CASCADE,
    token_hash  TEXT NOT NULL UNIQUE,
    expires_at  TEXT NOT NULL,
    used_at     TEXT,
    created_at  TEXT NOT NULL
);

-- Shared fixed-window login limiter. Keys are SHA-256 hashes, not raw IPs or
-- email addresses. SQLite is already required, so this avoids Redis while
-- keeping counters consistent across Gunicorn workers.
CREATE TABLE IF NOT EXISTS login_rate_limits (
    key_hash       TEXT PRIMARY KEY,
    attempts       INTEGER NOT NULL,
    window_started REAL NOT NULL
);

-- Every stored upload is owned by exactly one account.
CREATE TABLE IF NOT EXISTS uploads (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    stored_filename TEXT NOT NULL UNIQUE,
    original_name   TEXT NOT NULL DEFAULT '',
    content_type    TEXT NOT NULL DEFAULT '',
    size_bytes      INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL
);

-- Idempotency ledger for guest migration batches.
CREATE TABLE IF NOT EXISTS guest_import_batches (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    client_batch_id TEXT NOT NULL,
    device_id       TEXT NOT NULL DEFAULT '',
    summary_json    TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL,
    UNIQUE (user_id, client_batch_id)
);

CREATE TABLE IF NOT EXISTS guest_import_items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    batch_id   INTEGER REFERENCES guest_import_batches(id) ON DELETE SET NULL,
    entity     TEXT NOT NULL,
    local_uid  TEXT NOT NULL,
    server_id  INTEGER,
    created_at TEXT NOT NULL,
    UNIQUE (user_id, entity, local_uid)
);

-- Idempotency ledger for ordinary cloud writes (POST/PATCH/DELETE retries).
CREATE TABLE IF NOT EXISTS idempotency_keys (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    request_key   TEXT NOT NULL,
    method        TEXT NOT NULL,
    path          TEXT NOT NULL,
    status_code   INTEGER NOT NULL,
    response_json TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    expires_at    TEXT NOT NULL,
    UNIQUE (user_id, request_key)
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version    TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_auth_accounts_email ON auth_accounts(email);
CREATE INDEX IF NOT EXISTS idx_verification_account ON email_verification_tokens(account_id, expires_at);
CREATE INDEX IF NOT EXISTS idx_uploads_user ON uploads(user_id, id);
CREATE INDEX IF NOT EXISTS idx_guest_import_user_batch ON guest_import_batches(user_id, client_batch_id);
CREATE INDEX IF NOT EXISTS idx_guest_import_items_user ON guest_import_items(user_id, entity, local_uid);
CREATE INDEX IF NOT EXISTS idx_idempotency_user_key ON idempotency_keys(user_id, request_key);
CREATE INDEX IF NOT EXISTS idx_idempotency_expiry ON idempotency_keys(expires_at);

CREATE INDEX IF NOT EXISTS idx_tasks_user_status ON tasks(user_id, status);
CREATE INDEX IF NOT EXISTS idx_tasks_user_due ON tasks(user_id, due_date);
CREATE INDEX IF NOT EXISTS idx_tasks_user_planned ON tasks(user_id, planned_date);
CREATE INDEX IF NOT EXISTS idx_grades_user_date ON grades(user_id, exam_date);
CREATE INDEX IF NOT EXISTS idx_grades_user_subject ON grades(user_id, subject);
CREATE INDEX IF NOT EXISTS idx_notes_user_updated ON notes(user_id, updated_at);
CREATE INDEX IF NOT EXISTS idx_sessions_user_started ON study_sessions(user_id, started_at);
CREATE INDEX IF NOT EXISTS idx_sessions_user_subject ON study_sessions(user_id, subject);
CREATE INDEX IF NOT EXISTS idx_errors_user_subject ON error_records(user_id, subject);
CREATE INDEX IF NOT EXISTS idx_flashcards_user_due ON flashcards(user_id, next_review_date);
CREATE INDEX IF NOT EXISTS idx_achievements_user ON achievements(user_id);
CREATE INDEX IF NOT EXISTS idx_demo_records_table ON demo_records(table_name, record_id);
