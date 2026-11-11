"""Dashboard aggregation built from persisted StudyFlow data."""

from __future__ import annotations

from datetime import date, timedelta

from ..db import query_all, query_one
from ..utils.serializers import (
    serialize_achievement,
    serialize_grade,
    serialize_session,
    serialize_task,
    serialize_user,
)
from ..utils.timeutils import greeting_for_now, now_local, now_iso, today_iso
from .achievements import achievement_stats, evaluate_achievements
from .constants import ACHIEVEMENT_DEFS


def _streak_days(user_id: int) -> int:
    rows = query_all(
        """
        SELECT DISTINCT substr(started_at, 1, 10) AS day
        FROM study_sessions WHERE user_id = ?
        ORDER BY day DESC
        """,
        (user_id,),
    )
    days = [row["day"] for row in rows if row["day"]]
    if not days:
        return 0
    today = date.fromisoformat(today_iso())
    yesterday = today - timedelta(days=1)
    day_set = {date.fromisoformat(day) for day in days}
    cursor = today if today in day_set else yesterday if yesterday in day_set else None
    if cursor is None:
        return 0
    count = 0
    while cursor in day_set:
        count += 1
        cursor -= timedelta(days=1)
    return count


def _week_activity(user_id: int) -> list[dict]:
    today = date.fromisoformat(today_iso())
    start = today - timedelta(days=6)
    rows = query_all(
        """
        SELECT substr(started_at, 1, 10) AS day, SUM(duration_minutes) AS minutes,
               COUNT(*) AS sessions
        FROM study_sessions
        WHERE user_id = ? AND substr(started_at, 1, 10) >= ?
        GROUP BY substr(started_at, 1, 10)
        """,
        (user_id, start.isoformat()),
    )
    by_day = {row["day"]: dict(row) for row in rows}
    labels = ["一", "二", "三", "四", "五", "六", "日"]
    result = []
    for offset in range(7):
        current = start + timedelta(days=offset)
        key = current.isoformat()
        result.append(
            {
                "date": key,
                "weekday": labels[current.weekday()],
                "is_today": key == today_iso(),
                "minutes": int(by_day.get(key, {}).get("minutes") or 0),
                "sessions": int(by_day.get(key, {}).get("sessions") or 0),
            }
        )
    return result


def build_dashboard(user_id: int) -> dict:
    user = query_one("SELECT * FROM users WHERE id = ?", (user_id,))
    today = today_iso()
    now = now_local()

    # Today's task set: explicitly planned/due today + open overdue tasks.
    today_rows = query_all(
        """
        SELECT * FROM tasks
        WHERE user_id = ?
          AND (
            planned_date = ? OR due_date = ?
            OR (status != 'completed' AND due_date < ?)
          )
        ORDER BY
          CASE status WHEN 'completed' THEN 1 ELSE 0 END,
          CASE priority WHEN 1 THEN 0 WHEN 2 THEN 1 ELSE 2 END,
          COALESCE(planned_start, '23:59'),
          id
        LIMIT 12
        """,
        (user_id, today, today, today),
    )
    fallback_used = not today_rows
    # Fallback keeps the dashboard useful when nothing is explicitly planned.
    if fallback_used:
        today_rows = query_all(
            """
            SELECT * FROM tasks
            WHERE user_id = ? AND status != 'completed'
            ORDER BY
              CASE WHEN due_date IS NULL THEN 1 ELSE 0 END,
              due_date ASC,
              CASE priority WHEN 1 THEN 0 WHEN 2 THEN 1 ELSE 2 END,
              id
            LIMIT 5
            """,
            (user_id,),
        )
    today_tasks = [serialize_task(row, today=today) for row in today_rows]
    completed_today = [task for task in today_tasks if task["status"] == "completed"]
    today_completion_rate = (
        round(len(completed_today) / len(today_tasks) * 100) if today_tasks else 0
    )

    task_counts = query_one(
        """
        SELECT
          COUNT(*) AS total,
          SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending,
          SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) AS in_progress,
          SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
          SUM(CASE WHEN status != 'completed' AND due_date < ? THEN 1 ELSE 0 END) AS overdue,
          SUM(CASE WHEN status != 'completed' AND due_date = ? THEN 1 ELSE 0 END) AS due_today
        FROM tasks WHERE user_id = ?
        """,
        (today, today, user_id),
    )
    task_counts = dict(task_counts) if task_counts else {}

    session_today = query_one(
        """
        SELECT COALESCE(SUM(duration_minutes), 0) AS minutes, COUNT(*) AS sessions
        FROM study_sessions
        WHERE user_id = ? AND substr(started_at, 1, 10) = ?
        """,
        (user_id, today),
    )
    week_minutes_row = query_one(
        """
        SELECT COALESCE(SUM(duration_minutes), 0) AS minutes, COUNT(*) AS sessions
        FROM study_sessions
        WHERE user_id = ? AND substr(started_at, 1, 10) >= ?
        """,
        (user_id, (date.fromisoformat(today) - timedelta(days=6)).isoformat()),
    )
    total_study = query_one(
        "SELECT COALESCE(SUM(duration_minutes), 0) AS minutes FROM study_sessions WHERE user_id = ?",
        (user_id,),
    )

    grade_rows = query_all(
        """
        SELECT * FROM grades WHERE user_id = ?
        ORDER BY exam_date DESC, id DESC LIMIT 8
        """,
        (user_id,),
    )
    recent_grades = []
    seen_subjects = set()
    for row in grade_rows:
        record = serialize_grade(row)
        if record["subject"] in seen_subjects:
            continue
        seen_subjects.add(record["subject"])
        # Find the immediately previous grade in this subject for a delta.
        prior = query_one(
            """
            SELECT score, max_score FROM grades
            WHERE user_id = ? AND subject = ? AND exam_date < ?
            ORDER BY exam_date DESC, id DESC LIMIT 1
            """,
            (user_id, record["subject"], record["exam_date"]),
        )
        if prior:
            prior_percentage = prior["score"] / prior["max_score"] * 100
            record["delta"] = round(record["percentage"] - prior_percentage, 1)
        else:
            record["delta"] = None
        recent_grades.append(record)
        if len(recent_grades) >= 4:
            break

    session_rows = query_all(
        """
        SELECT s.*, t.title AS task_title
        FROM study_sessions s
        LEFT JOIN tasks t ON t.id = s.task_id
        WHERE s.user_id = ?
        ORDER BY s.started_at DESC LIMIT 5
        """,
        (user_id,),
    )
    recent_sessions = [serialize_session(row) for row in session_rows]

    # Evaluate before reading so newly reachable achievements appear immediately.
    evaluate_achievements(user_id)
    achievement_rows = query_all(
        """
        SELECT * FROM achievements WHERE user_id = ?
        ORDER BY unlocked_at DESC LIMIT 4
        """,
        (user_id,),
    )
    stats = achievement_stats(user_id)
    unlocked_total = query_one(
        "SELECT COUNT(*) AS count FROM achievements WHERE user_id = ?", (user_id,)
    )

    activity = _week_activity(user_id)
    week_minutes = sum(item["minutes"] for item in activity)
    daily_goal = int(user["daily_goal_minutes"]) if user else 120
    focus_today = int(session_today["minutes"]) if session_today else 0

    upcoming_grades = recent_grades[:3]
    return {
        "server_time": now_iso(),
        "date": today,
        "date_label": f"{now.year}年{now.month}月{now.day}日",
        "weekday_label": "星期" + "一二三四五六日"[now.weekday()],
        "greeting": greeting_for_now(),
        "user": serialize_user(user) if user else None,
        "stats": {
            "today_tasks_total": len(today_tasks),
            "today_tasks_completed": len(completed_today),
            "today_completion_rate": today_completion_rate,
            "today_focus_minutes": focus_today,
            "today_sessions": int(session_today["sessions"]) if session_today else 0,
            "daily_goal_minutes": daily_goal,
            "goal_progress": min(100, round(focus_today / daily_goal * 100)) if daily_goal else 0,
            "week_focus_minutes": week_minutes,
            "week_sessions": int(week_minutes_row["sessions"]) if week_minutes_row else 0,
            "total_study_minutes": int(total_study["minutes"]) if total_study else 0,
            "open_tasks": (task_counts.get("pending") or 0)
            + (task_counts.get("in_progress") or 0),
            "overdue_tasks": task_counts.get("overdue") or 0,
            "due_today": task_counts.get("due_today") or 0,
            "streak_days": _streak_days(user_id),
            "achievements_unlocked": unlocked_total["count"] if unlocked_total else 0,
            "achievements_total": len(ACHIEVEMENT_DEFS),
            "study_days": stats.get("study_days", 0),
            "recent_average": (
                round(sum(item["percentage"] for item in incoming) / len(incoming), 1)
                if (incoming := recent_grades)
                else None
            ),
        },
        "today_tasks": today_tasks,
        "recent_grades": upcoming_grades,
        "recent_sessions": recent_sessions,
        "achievements": [serialize_achievement(row) for row in achievement_rows],
        "week_activity": activity,
        "task_counts": task_counts,
        "has_fallback_tasks": fallback_used,
        "today": today,
    }
