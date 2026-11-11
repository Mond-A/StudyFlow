"""Achievement rules. Definitions live in code; unlock state is persisted."""

from __future__ import annotations

from ..db import execute, query_one
from ..utils.timeutils import now_iso
from .constants import ACHIEVEMENT_DEFS


def achievement_stats(user_id: int) -> dict:
    row = query_one(
        """
        SELECT
          (SELECT COUNT(*) FROM tasks WHERE user_id = ? AND status = 'completed') AS tasks_completed,
          (SELECT COALESCE(SUM(duration_minutes), 0) FROM study_sessions WHERE user_id = ?) AS study_minutes,
          (SELECT COUNT(*) FROM study_sessions WHERE user_id = ?) AS sessions_count,
          (SELECT COUNT(DISTINCT substr(started_at, 1, 10)) FROM study_sessions WHERE user_id = ?) AS study_days,
          (SELECT COUNT(*) FROM notes WHERE user_id = ?) AS notes_count,
          (SELECT COUNT(*) FROM grades WHERE user_id = ?) AS grades_count,
          (SELECT COUNT(*) FROM flashcards WHERE user_id = ?) AS flashcards_count
        """,
        (user_id,) * 7,
    )
    return dict(row) if row else {}


def _meets(criterion: str, stats: dict) -> bool:
    # Criteria are trusted constants, not user input.
    try:
        left, right = [part.strip() for part in criterion.split(">=")]
        return int(stats.get(left, 0)) >= int(right)
    except (ValueError, AttributeError):
        return False


def evaluate_achievements(user_id: int) -> list[dict]:
    """Unlock any newly earned achievements and return the new unlocks."""
    stats = achievement_stats(user_id)
    unlocked = []
    for definition in ACHIEVEMENT_DEFS:
        if not _meets(definition["criterion"], stats):
            continue
        cursor = execute(
            """
            INSERT OR IGNORE INTO achievements
                (user_id, code, title, description, icon, unlocked_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                definition["code"],
                definition["title"],
                definition["description"],
                definition["icon"],
                now_iso(),
            ),
        )
        if cursor.rowcount:
            unlocked.append({**definition, "unlocked_at": now_iso()})
    return unlocked


def list_achievements(user_id: int) -> dict:
    stats = achievement_stats(user_id)
    rows = query_one(
        "SELECT COUNT(*) AS count FROM achievements WHERE user_id = ?", (user_id,)
    )
    unlocked_rows = execute(
        "SELECT * FROM achievements WHERE user_id = ?", (user_id,)
    ).fetchall()
    by_code = {row["code"]: row for row in unlocked_rows}
    items = []
    for definition in ACHIEVEMENT_DEFS:
        stored = by_code.get(definition["code"])
        items.append(
            {
                "code": definition["code"],
                "title": definition["title"],
                "description": definition["description"],
                "icon": definition["icon"],
                "criterion": definition["criterion"],
                "unlocked": stored is not None,
                "unlocked_at": stored["unlocked_at"] if stored else None,
            }
        )
    unlocked_count = sum(1 for item in items if item["unlocked"])
    return {
        "items": items,
        "unlocked_count": unlocked_count,
        "total": len(items),
        "stats": stats,
        "summary": {
            "tasks_completed": stats.get("tasks_completed", 0),
            "study_minutes": stats.get("study_minutes", 0),
            "study_days": stats.get("study_days", 0),
            "notes_count": stats.get("notes_count", 0),
            "grades_count": stats.get("grades_count", 0),
            "flashcards_count": stats.get("flashcards_count", 0),
        },
        "_db_count": rows["count"] if rows else 0,
    }
