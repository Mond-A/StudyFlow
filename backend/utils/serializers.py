"""Database row -> API JSON serializers. Keep field names stable for the SPA."""

from __future__ import annotations

import json
from datetime import date

from .timeutils import parse_date, today_iso


def _loads(value, fallback):
    if value in (None, ""):
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def serialize_user(row) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"],
        "email": row["email"],
        "avatar_color": row["avatar_color"],
        "daily_goal_minutes": row["daily_goal_minutes"],
        "pomodoro_minutes": row["pomodoro_minutes"],
        "short_break_minutes": row["short_break_minutes"],
        "long_break_minutes": row["long_break_minutes"],
        "timezone": row["timezone"],
        "created_at": row["created_at"],
    }


def serialize_task(row, *, today: str | None = None) -> dict:
    current = today or today_iso()
    due_date = row["due_date"]
    days_until_due = None
    is_overdue = False
    if due_date:
        try:
            days_until_due = (parse_date(due_date) - date.fromisoformat(current)).days
            is_overdue = row["status"] != "completed" and days_until_due < 0
        except ValueError:
            days_until_due = None
    return {
        "id": row["id"],
        "title": row["title"],
        "subject": row["subject"],
        "description": row["description"],
        "due_date": due_date,
        "estimated_minutes": row["estimated_minutes"],
        "actual_minutes": row["actual_minutes"],
        "difficulty": row["difficulty"],
        "status": row["status"],
        "priority": row["priority"],
        "planned_date": row["planned_date"],
        "planned_start": row["planned_start"],
        "planned_minutes": row["planned_minutes"],
        "source": row["source"],
        "ai_meta": _loads(row["ai_meta"], None),
        "completed_at": row["completed_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "is_overdue": is_overdue,
        "days_until_due": days_until_due,
    }


def serialize_grade(row) -> dict:
    percentage = round((row["score"] / row["max_score"]) * 100, 1)
    if percentage >= 90:
        level = "优秀"
    elif percentage >= 80:
        level = "良好"
    elif percentage >= 60:
        level = "及格"
    else:
        level = "待提升"
    return {
        "id": row["id"],
        "subject": row["subject"],
        "exam_name": row["exam_name"],
        "score": row["score"],
        "max_score": row["max_score"],
        "percentage": percentage,
        "level": level,
        "exam_date": row["exam_date"],
        "notes": row["notes"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def serialize_note_summary(row) -> dict:
    content = row["content_markdown"] or ""
    plain = content.replace("#", "").replace("*", "").replace("`", "").strip()
    return {
        "id": row["id"],
        "title": row["title"],
        "subject": row["subject"],
        "snippet": plain[:140],
        "content_length": len(content),
        "source_image": row["source_image"],
        "has_audit": bool(row["audit_report"]),
        "has_graph": bool(row["knowledge_graph"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def serialize_note(row, *, full: bool = True) -> dict:
    payload = serialize_note_summary(row)
    if full:
        payload["content_markdown"] = row["content_markdown"]
        payload["audit_report"] = _loads(row["audit_report"], None)
        payload["knowledge_graph"] = _loads(row["knowledge_graph"], None)
    return payload


def serialize_session(row) -> dict:
    return {
        "id": row["id"],
        "task_id": row["task_id"],
        "task_title": row["task_title"] if "task_title" in row.keys() else None,
        "subject": row["subject"],
        "duration_minutes": row["duration_minutes"],
        "session_type": row["session_type"],
        "started_at": row["started_at"],
        "ended_at": row["ended_at"],
        "note": row["note"],
        "created_at": row["created_at"],
    }


def serialize_error_record(row) -> dict:
    return {
        "id": row["id"],
        "subject": row["subject"],
        "question": row["question"],
        "student_answer": row["student_answer"],
        "correct_answer": row["correct_answer"],
        "analysis": row["analysis"],
        "knowledge_points": _loads(row["knowledge_points"], []),
        "mastery": row["mastery"],
        "source": row["source"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def serialize_flashcard(row) -> dict:
    today = today_iso()
    next_review = row["next_review_date"]
    is_due = not next_review or next_review <= today
    return {
        "id": row["id"],
        "note_id": row["note_id"],
        "front": row["front"],
        "back": row["back"],
        "subject": row["subject"],
        "mastery_level": row["mastery_level"],
        "review_count": row["review_count"],
        "next_review_date": next_review,
        "last_reviewed_at": row["last_reviewed_at"],
        "is_due": is_due,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def serialize_achievement(row) -> dict:
    return {
        "id": row["id"],
        "code": row["code"],
        "title": row["title"],
        "description": row["description"],
        "icon": row["icon"],
        "unlocked_at": row["unlocked_at"],
    }
