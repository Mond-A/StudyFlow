"""Deterministic study planner.

AI may suggest per-task estimates when homework is recognised, but the planner
uses transparent local rules and historical actual durations. AI output never
silently overwrites user-edited fields.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from ..db import get_db, query_all, query_one, transaction
from ..utils.timeutils import now_iso, today_iso


def _history_ratios(user_id: int) -> tuple[dict[str, float], float | None]:
    rows = query_all(
        """
        SELECT subject,
               AVG(CASE WHEN estimated_minutes > 0
                        THEN CAST(actual_minutes AS REAL) / estimated_minutes END) AS ratio,
               COUNT(*) AS sample_count
        FROM tasks
        WHERE user_id = ? AND status = 'completed'
          AND actual_minutes > 0 AND estimated_minutes > 0
        GROUP BY subject
        """,
        (user_id,),
    )
    by_subject = {}
    total_weighted = []
    for row in rows:
        if row["ratio"] and row["sample_count"]:
            ratio = min(1.8, max(0.6, float(row["ratio"])))
            by_subject[row["subject"]] = round(ratio, 2)
            total_weighted.extend([ratio] * int(row["sample_count"]))
    overall = round(sum(total_weighted) / len(total_weighted), 2) if total_weighted else None
    return by_subject, overall


def _urgency(task, today: date) -> tuple:
    due = task["due_date"]
    if due:
        try:
            days = (datetime.strptime(due, "%Y-%m-%d").date() - today).days
        except ValueError:
            days = 999
    else:
        days = 999
    priority = int(task["priority"] or 2)
    difficulty = int(task["difficulty"] or 3)
    # Earlier tuple wins: overdue/urgent, high priority, harder tasks.
    return (days, priority, -difficulty, task["id"])


def build_plan(
    user_id: int,
    *,
    available_minutes: int,
    start_time: str,
    plan_date: str,
    task_ids: list[int] | None = None,
) -> dict:
    today = date.fromisoformat(today_iso())
    try:
        target_date = date.fromisoformat(plan_date)
    except ValueError:
        target_date = today

    query = """
        SELECT * FROM tasks
        WHERE user_id = ? AND status != 'completed'
    """
    params: list = [user_id]
    if task_ids:
        placeholders = ",".join("?" for _ in task_ids)
        query += f" AND id IN ({placeholders})"
        params.extend(task_ids)
    tasks = query_all(query, params)
    ordered = sorted(tasks, key=lambda item: _urgency(item, today))

    ratios, overall_ratio = _history_ratios(user_id)
    # Keep plan inside the selected calendar day.
    start_dt = datetime.strptime(f"{plan_date} {start_time}", "%Y-%m-%d %H:%M")
    end_of_day = datetime.combine(target_date + timedelta(days=1), datetime.min.time())
    minutes_left_today = max(0, int((end_of_day - start_dt).total_seconds() // 60))
    usable = min(available_minutes, minutes_left_today)

    schedule = []
    unscheduled = []
    remaining = usable
    cursor = start_dt
    for task in ordered:
        if remaining < 10:
            unscheduled.append(
                {
                    "id": task["id"],
                    "title": task["title"],
                    "subject": task["subject"],
                    "estimated_minutes": task["estimated_minutes"],
                    "reason": "可用时间不足（至少需要 10 分钟）",
                }
            )
            continue

        ratio = ratios.get(task["subject"], overall_ratio or 1.0)
        adjusted = max(10, int(round(task["estimated_minutes"] * ratio)))
        adjusted = min(adjusted, 240)
        planned = min(adjusted, remaining)
        partial = planned < adjusted
        reason_parts = []
        due = task["due_date"]
        if due:
            try:
                days = (date.fromisoformat(due) - target_date).days
            except ValueError:
                days = None
            if days is not None:
                if days < 0:
                    reason_parts.append("已逾期，优先处理")
                elif days == 0:
                    reason_parts.append("今天截止")
                elif days == 1:
                    reason_parts.append("明天截止")
        if task["priority"] == 1:
            reason_parts.append("高优先级")
        if task["difficulty"] >= 4:
            reason_parts.append("难度较高，建议先完成")
        if ratio != 1.0:
            reason_parts.append(
                f"根据历史实际耗时调整为约 {adjusted} 分钟"
            )
        if partial:
            reason_parts.append("本次仅安排部分时间，剩余部分稍后继续")
        if not reason_parts:
            reason_parts.append("按截止时间与优先级排序")

        schedule.append(
            {
                "task_id": task["id"],
                "title": task["title"],
                "subject": task["subject"],
                "difficulty": task["difficulty"],
                "due_date": task["due_date"],
                "estimated_minutes": task["estimated_minutes"],
                "suggested_minutes": adjusted,
                "planned_minutes": planned,
                "start_time": cursor.strftime("%H:%M"),
                "end_time": (cursor + timedelta(minutes=planned)).strftime("%H:%M"),
                "partial": partial,
                "reason": "；".join(reason_parts),
            }
        )
        remaining -= planned
        cursor += timedelta(minutes=planned)

    if not ordered:
        status_note = "当前没有待安排的任务。"
    elif not schedule:
        status_note = "可用时间不足，未能生成安排。"
    elif unscheduled:
        status_note = "部分任务因本次可用时间不足尚未安排。"
    else:
        status_note = "所有待办任务均已纳入本次安排。"

    return {
        "plan_date": plan_date,
        "start_time": start_time,
        "available_minutes": available_minutes,
        "usable_minutes": usable,
        "scheduled_minutes": usable - remaining,
        "remaining_minutes": remaining,
        "history_ratio": overall_ratio,
        "subject_history_ratio": ratios,
        "schedule": schedule,
        "unscheduled_tasks": unscheduled,
        "summary": status_note,
        "notice": (
            "排期由 StudyFlow 本地规则生成，参考截止时间、优先级、难度与历史实际耗时；"
            "你可以自由修改任务时长后再应用。"
        ),
        "beyond_midnight": minutes_left_today < available_minutes,
    }


def apply_plan(user_id: int, items: list[dict], plan_date: str) -> int:
    """Persist an approved plan atomically. User-owned tasks only."""
    count = 0
    with transaction():
        db = get_db()
        for item in items:
            task_id = int(item["task_id"])
            start_time = item.get("start_time") or item.get("planned_start")
            planned_minutes = int(item.get("planned_minutes") or 0)
            if planned_minutes <= 0:
                continue
            cursor = query_one(
                "SELECT id FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id)
            )
            if not cursor:
                continue
            db.execute(
                """
                UPDATE tasks
                SET planned_date = ?, planned_start = ?, planned_minutes = ?, updated_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (plan_date, start_time, planned_minutes, now_iso(), task_id, user_id),
            )
            count += 1
    return count
