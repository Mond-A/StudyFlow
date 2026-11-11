"""Daily study report computed locally from persisted data."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from ..db import query_all, query_one
from ..utils.serializers import serialize_error_record, serialize_grade, serialize_note_summary
from ..utils.timeutils import now_iso, today_iso


def build_daily_report(user_id: int, day: str) -> dict:
    user = query_one("SELECT * FROM users WHERE id = ?", (user_id,))
    task_rows = query_all(
        """
        SELECT * FROM tasks
        WHERE user_id = ?
          AND (planned_date = ? OR due_date = ? OR substr(completed_at, 1, 10) = ?)
        ORDER BY COALESCE(planned_start, '23:59'), id
        """,
        (user_id, day, day, day),
    )
    completed = [row for row in task_rows if row["status"] == "completed"]
    pending = [row for row in task_rows if row["status"] != "completed"]
    sessions = query_all(
        """
        SELECT * FROM study_sessions
        WHERE user_id = ? AND substr(started_at, 1, 10) = ?
        ORDER BY started_at ASC
        """,
        (user_id, day),
    )
    minutes_by_subject = defaultdict(int)
    for session in sessions:
        minutes_by_subject[session["subject"]] += int(session["duration_minutes"])
    total_minutes = sum(int(session["duration_minutes"]) for session in sessions)
    pomodoros = sum(
        1
        for session in sessions
        if session["session_type"] == "pomodoro"
    )

    grade_rows = query_all(
        "SELECT * FROM grades WHERE user_id = ? AND exam_date = ? ORDER BY id",
        (user_id, day),
    )
    grades = [serialize_grade(row) for row in grade_rows]
    note_rows = query_all(
        "SELECT * FROM notes WHERE user_id = ? AND substr(created_at, 1, 10) = ?",
        (user_id, day),
    )
    notes = [serialize_note_summary(row) for row in note_rows]
    error_rows = query_all(
        "SELECT * FROM error_records WHERE user_id = ? AND substr(created_at, 1, 10) = ?",
        (user_id, day),
    )
    errors = [serialize_error_record(row) for row in error_rows]
    reviewed = query_one(
        """
        SELECT COUNT(*) AS count FROM flashcards
        WHERE user_id = ? AND substr(last_reviewed_at, 1, 10) = ?
        """,
        (user_id, day),
    )
    unlocked = query_all(
        """
        SELECT code, title, icon, unlocked_at FROM achievements
        WHERE user_id = ? AND substr(unlocked_at, 1, 10) = ?
        ORDER BY unlocked_at
        """,
        (user_id, day),
    )
    daily_goal = int(user["daily_goal_minutes"]) if user else 120
    completion_rate = (
        round(len(completed) / len(task_rows) * 100) if task_rows else 0
    )
    goal_progress = min(100, round(total_minutes / daily_goal * 100)) if daily_goal else 0

    narrative = []
    if total_minutes:
        narrative.append(
            f"今天共专注学习 {total_minutes} 分钟，完成 {len(sessions)} 次学习记录，"
            f"达到每日目标的 {goal_progress}%。"
        )
    else:
        narrative.append("今天还没有专注学习记录，可以从一个 25 分钟番茄钟开始。")
    if task_rows:
        narrative.append(
            f"今日相关任务 {len(task_rows)} 个，已完成 {len(completed)} 个，"
            f"完成率 {completion_rate}%。"
        )
    else:
        narrative.append("今天还没有安排学习任务。")
    if minutes_by_subject:
        top = sorted(minutes_by_subject.items(), key=lambda item: item[1], reverse=True)[0]
        narrative.append(f"投入时间最多的学科是{top[0]}（{top[1]} 分钟）。")
    if pending:
        narrative.append(f"仍有 {len(pending)} 个任务未完成，可在 Planner 中重新安排时间。")
    if grades:
        narrative.append(f"今天记录了 {len(grades)} 条新成绩，已同步到成绩分析。")
    if errors:
        narrative.append(f"新增 {len(errors)} 道错题，记得安排一次复盘。")

    suggestions = []
    if not sessions:
        suggestions.append("先完成一个 25 分钟番茄钟，降低开始学习的阻力。")
    elif goal_progress < 60:
        suggestions.append("今日专注时长尚未达到目标，可再安排一个短时段。")
    elif goal_progress >= 100:
        suggestions.append("今日学习目标已达成，注意休息和复盘，不需要盲目加时。")
    if pending:
        suggestions.append("把未完成任务按“截止时间 + 难度”重新排期，避免拖到逾期。")
    if errors:
        suggestions.append("从今天新增的错题中选 1-2 道，写出错误原因和正确思路。")
    if not task_rows and not sessions:
        suggestions.append("先安排一个最小任务（15-25 分钟），让今天有明确的完成目标。")
    if not suggestions:
        suggestions.append("保持当前节奏，睡前用 5 分钟回顾今天学到的 3 个要点。")

    weekday_labels = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    parsed = date.fromisoformat(day)
    return {
        "date": day,
        "date_label": f"{parsed.year}年{parsed.month}月{parsed.day}日",
        "weekday": weekday_labels[parsed.weekday()],
        "is_today": day == today_iso(),
        "generated_at": now_iso(),
        "user": {"display_name": user["display_name"] if user else "同学"},
        "goal": {
            "target_minutes": daily_goal,
            "actual_minutes": total_minutes,
            "progress": goal_progress,
        },
        "tasks": {
            "total": len(task_rows),
            "completed": len(completed),
            "pending": len(pending),
            "completion_rate": completion_rate,
            "items": [
                {
                    "id": row["id"],
                    "title": row["title"],
                    "subject": row["subject"],
                    "status": row["status"],
                    "actual_minutes": row["actual_minutes"],
                }
                for row in task_rows
            ],
            "pending_items": [
                {"id": row["id"], "title": row["title"], "subject": row["subject"]}
                for row in pending
            ],
        },
        "study": {
            "total_minutes": total_minutes,
            "session_count": len(sessions),
            "pomodoros": pomodoros,
            "subjects": [
                {"subject": subject, "minutes": minutes}
                for subject, minutes in sorted(
                    minutes_by_subject.items(), key=lambda item: item[1], reverse=True
                )
            ],
            "sessions": [
                {
                    "id": session["id"],
                    "subject": session["subject"],
                    "duration_minutes": session["duration_minutes"],
                    "session_type": session["session_type"],
                    "started_at": session["started_at"],
                }
                for session in sessions
            ],
        },
        "grades": grades,
        "notes": notes,
        "errors": [
            {"id": item["id"], "subject": item["subject"], "knowledge_points": item["knowledge_points"]}
            for item in errors
        ],
        "flashcards_reviewed": int(reviewed["count"]) if reviewed else 0,
        "achievements": [dict(row) for row in unlocked],
        "narrative": narrative,
        "suggestions": suggestions,
        "notice": "本报告由 StudyFlow 根据本地数据自动汇总，不包含外部 AI 生成内容。",
    }
