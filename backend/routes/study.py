"""Study sessions, achievements and focus statistics."""

from __future__ import annotations

from datetime import date, timedelta

from flask import Blueprint, request

from ..db import execute, get_current_user_id, query_all, query_one
from ..services.achievements import (
    achievement_stats,
    evaluate_achievements,
    list_achievements,
)
from ..utils.exceptions import APIError, NotFound
from ..utils.responses import success
from ..utils.serializers import serialize_session
from ..utils.timeutils import (
    get_timezone,
    now_iso,
    now_local,
    parse_date,
    today_iso,
)
from ..utils.validators import (
    choice_field,
    int_field,
    json_body,
    optional_datetime,
    query_int,
    text_field,
)

bp = Blueprint("study", __name__)

SESSION_TYPES = {"pomodoro", "free", "manual", "task"}


def _session_or_404(user_id: int, session_id: int):
    row = query_one(
        "SELECT * FROM study_sessions WHERE id = ? AND user_id = ?",
        (session_id, user_id),
    )
    if not row:
        raise NotFound("学习记录不存在")
    return row


def _focus_summary(user_id: int) -> dict:
    today = today_iso()
    week_start = (date.fromisoformat(today) - timedelta(days=6)).isoformat()
    today_row = query_one(
        """
        SELECT COALESCE(SUM(duration_minutes), 0) AS minutes, COUNT(*) AS sessions
        FROM study_sessions WHERE user_id = ? AND substr(started_at, 1, 10) = ?
        """,
        (user_id, today),
    )
    week_row = query_one(
        """
        SELECT COALESCE(SUM(duration_minutes), 0) AS minutes, COUNT(*) AS sessions
        FROM study_sessions WHERE user_id = ? AND substr(started_at, 1, 10) >= ?
        """,
        (user_id, week_start),
    )
    total_row = query_one(
        """
        SELECT COALESCE(SUM(duration_minutes), 0) AS minutes, COUNT(*) AS sessions
        FROM study_sessions WHERE user_id = ?
        """,
        (user_id,),
    )
    by_subject = query_all(
        """
        SELECT subject, SUM(duration_minutes) AS minutes, COUNT(*) AS sessions
        FROM study_sessions WHERE user_id = ?
        GROUP BY subject ORDER BY minutes DESC LIMIT 10
        """,
        (user_id,),
    )
    days = []
    rows = query_all(
        """
        SELECT substr(started_at, 1, 10) AS day, SUM(duration_minutes) AS minutes
        FROM study_sessions
        WHERE user_id = ? AND substr(started_at, 1, 10) >= ?
        GROUP BY substr(started_at, 1, 10)
        """,
        (user_id, week_start),
    )
    by_day = {row["day"]: int(row["minutes"]) for row in rows}
    labels = ["一", "二", "三", "四", "五", "六", "日"]
    for offset in range(7):
        current = date.fromisoformat(week_start) + timedelta(days=offset)
        days.append(
            {
                "date": current.isoformat(),
                "weekday": labels[current.weekday()],
                "minutes": by_day.get(current.isoformat(), 0),
                "is_today": current.isoformat() == today,
            }
        )
    stats = achievement_stats(user_id)
    return {
        "today_minutes": int(today_row["minutes"]) if today_row else 0,
        "today_sessions": int(today_row["sessions"]) if today_row else 0,
        "week_minutes": int(week_row["minutes"]) if week_row else 0,
        "week_sessions": int(week_row["sessions"]) if week_row else 0,
        "total_minutes": int(total_row["minutes"]) if total_row else 0,
        "total_sessions": int(total_row["sessions"]) if total_row else 0,
        "study_days": stats.get("study_days", 0),
        "by_subject": [dict(row) for row in by_subject],
        "week_activity": days,
    }


@bp.get("/study/sessions")
def list_sessions():
    user_id = get_current_user_id()
    date_filter = (request.args.get("date") or "").strip()
    subject = (request.args.get("subject") or "").strip()
    limit = query_int("limit", 50, minimum=1, maximum=300)
    conditions = ["s.user_id = ?"]
    params: list = [user_id]
    if date_filter:
        try:
            parse_date(date_filter, "date")
        except APIError:
            raise
        conditions.append("substr(s.started_at, 1, 10) = ?")
        params.append(date_filter)
    if subject and subject != "all":
        conditions.append("s.subject = ?")
        params.append(subject)
    rows = query_all(
        f"""
        SELECT s.*, t.title AS task_title
        FROM study_sessions s
        LEFT JOIN tasks t ON t.id = s.task_id AND t.user_id = s.user_id
        WHERE {' AND '.join(conditions)}
        ORDER BY s.started_at DESC LIMIT ?
        """,
        (*params, limit),
    )
    return success(
        {
            "sessions": [serialize_session(row) for row in rows],
            "summary": _focus_summary(user_id),
            "filters": {"date": date_filter or None, "subject": subject or "all"},
        }
    )


@bp.post("/study/sessions")
def create_session():
    user_id = get_current_user_id()
    data = json_body()
    subject = text_field(data, "subject", "学科", default="综合", max_length=30) or "综合"
    duration = int_field(
        data,
        "duration_minutes",
        "学习时长",
        required=True,
        minimum=1,
        maximum=720,
    )
    session_type = (
        choice_field(
            data,
            "session_type",
            "记录类型",
            SESSION_TYPES,
            default="pomodoro",
        )
        or "pomodoro"
    )
    note = text_field(data, "note", "备注", max_length=1000)
    started_at = optional_datetime(data.get("started_at"), "开始时间")
    ended_at = optional_datetime(data.get("ended_at"), "结束时间")
    task_id = data.get("task_id")
    if task_id not in (None, ""):
        try:
            task_id = int(task_id)
        except (TypeError, ValueError) as exc:
            raise APIError("任务 ID 无效", code="VALIDATION_ERROR", status_code=400) from exc
        owns_task = query_one(
            "SELECT id FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id)
        )
        if not owns_task:
            raise APIError("关联的任务不存在", code="TASK_NOT_FOUND", status_code=404)
    else:
        task_id = None

    now = now_local()
    if not started_at:
        start_dt = now - timedelta(minutes=duration)
        started_at = start_dt.isoformat()
    if not ended_at:
        try:
            from datetime import datetime

            end_dt = datetime.fromisoformat(started_at) + timedelta(minutes=duration)
            ended_at = end_dt.isoformat()
        except ValueError:
            ended_at = now.isoformat()

    cursor = execute(
        """
        INSERT INTO study_sessions
            (user_id, task_id, subject, duration_minutes, session_type,
             started_at, ended_at, note, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            task_id,
            subject,
            duration,
            session_type,
            started_at,
            ended_at,
            note,
            now_iso(),
        ),
    )
    unlocked = evaluate_achievements(user_id)
    row = query_one(
        """
        SELECT s.*, t.title AS task_title FROM study_sessions s
        LEFT JOIN tasks t ON t.id = s.task_id AND t.user_id = s.user_id
        WHERE s.id = ? AND s.user_id = ?
        """,
        (cursor.lastrowid, user_id),
    )
    return success(
        {"session": serialize_session(row), "unlocked_achievements": unlocked},
        status=201,
        message="学习记录已保存",
    )


@bp.delete("/study/sessions/<int:session_id>")
def delete_session(session_id: int):
    user_id = get_current_user_id()
    _session_or_404(user_id, session_id)
    execute(
        "DELETE FROM study_sessions WHERE id = ? AND user_id = ?",
        (session_id, user_id),
    )
    return success({"deleted_id": session_id}, message="学习记录已删除")


@bp.get("/study/stats")
def study_stats():
    user_id = get_current_user_id()
    return success(_focus_summary(user_id))


@bp.get("/achievements")
def get_achievements():
    user_id = get_current_user_id()
    result = list_achievements(user_id)
    result.pop("_db_count", None)
    return success(result)
