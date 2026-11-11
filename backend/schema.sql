-- StudyFlow SQLite schema (MVP, single-user ready with multi-user keys)
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
