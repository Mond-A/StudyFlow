"""Task CRUD and the deterministic study planner endpoints."""

from __future__ import annotations

import json

from flask import Blueprint, request

from ..db import execute, get_current_user_id, query_all, query_one
from ..services.achievements import evaluate_achievements
from ..services.planner import apply_plan, build_plan
from ..utils.exceptions import NotFound
from ..utils.responses import success
from ..utils.serializers import serialize_task
from ..utils.timeutils import now_iso, today_iso
from ..utils.validators import (
    bool_field,
    choice_field,
    date_field,
    int_field,
    json_body,
    query_int,
    text_field,
    time_field,
)

bp = Blueprint("tasks", __name__)
OPEN_STATUSES = {"pending", "in_progress"}


def _get_task_or_404(user_id: int, task_id: int):
    row = query_one(
        "SELECT * FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id)
    )
    if not row:
        raise NotFound("任务不存在或已被删除")
    return row


def _task_counts(user_id: int) -> dict:
    today = today_iso()
    row = query_one(
        """
        SELECT
          COUNT(*) AS total,
          SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending,
          SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) AS in_progress,
          SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
          SUM(CASE WHEN status != 'completed' AND due_date < ? THEN 1 ELSE 0 END) AS overdue,
          SUM(CASE WHEN status != 'completed' AND due_date = ? THEN 1 ELSE 0 END) AS due_today,
          COALESCE(SUM(CASE WHEN status != 'completed' THEN estimated_minutes ELSE 0 END), 0)
            AS open_estimated_minutes
        FROM tasks WHERE user_id = ?
        """,
        (today, today, user_id),
    )
    return dict(row) if row else {}


@bp.get("/tasks")
def list_tasks():
    user_id = get_current_user_id()
    status = (request.args.get("status") or "all").strip()
    if status not in {"all", "open", "pending", "in_progress", "completed", "history"}:
        status = "all"
    subject = (request.args.get("subject") or "").strip()
    search = (request.args.get("q") or "").strip()
    limit = query_int("limit", 100, minimum=1, maximum=300)

    conditions = ["user_id = ?"]
    params: list = [user_id]
    if status == "open":
        conditions.append("status != 'completed'")
    elif status == "completed":
        conditions.append("status = 'completed'")
    elif status == "history":
        conditions.append("status = 'completed'")
    elif status in OPEN_STATUSES:
        conditions.append("status = ?")
        params.append(status)
    if subject and subject != "all":
        conditions.append("subject = ?")
        params.append(subject)
    if search:
        conditions.append("(title LIKE ? OR description LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    if status in {"completed", "history"}:
        order = "completed_at DESC, id DESC"
    else:
        order = (
            "CASE status WHEN 'in_progress' THEN 0 WHEN 'pending' THEN 1 ELSE 2 END, "
            "CASE WHEN due_date IS NULL THEN 1 ELSE 0 END, due_date ASC, "
            "CASE priority WHEN 1 THEN 0 WHEN 2 THEN 1 ELSE 2 END, "
            "COALESCE(planned_start, '23:59'), id DESC"
        )
    rows = query_all(
        f"SELECT * FROM tasks WHERE {' AND '.join(conditions)} ORDER BY {order} LIMIT ?",
        (*params, limit),
    )
    tabs_counts = _task_counts(user_id)
    return success(
        {
            "tasks": [serialize_task(row) for row in rows],
            "counts": tabs_counts,
            "filters": {
                "status": status,
                "subject": subject or "all",
                "q": search,
            },
        }
    )


@bp.post("/tasks")
def create_task():
    user_id = get_current_user_id()
    data = json_body()
    title = text_field(data, "title", "任务标题", required=True, max_length=180)
    subject = text_field(data, "subject", "学科", default="综合", max_length=30) or "综合"
    description = text_field(data, "description", "任务说明", max_length=3000)
    due_date = date_field(data, "due_date", "截止日期")
    estimated = int_field(
        data, "estimated_minutes", "预计耗时", default=30, minimum=5, maximum=1440
    )
    difficulty = int_field(
        data, "difficulty", "难度", default=3, minimum=1, maximum=5
    )
    priority = int_field(data, "priority", "优先级", default=2, minimum=1, maximum=3)
    planned_date = date_field(data, "planned_date", "计划日期")
    planned_start = time_field(data, "planned_start", "计划开始时间")
    planned_minutes = int_field(
        data,
        "planned_minutes",
        "计划时长",
        default=None,
        minimum=1,
        maximum=1440,
    )
    source = choice_field(
        data,
        "source",
        "来源",
        {"manual", "ai", "import"},
        default="manual",
    )
    ai_meta = data.get("ai_meta")
    if ai_meta is not None and not isinstance(ai_meta, dict):
        ai_meta = None
    timestamp = now_iso()
    cursor = execute(
        """
        INSERT INTO tasks
            (user_id, title, subject, description, due_date, estimated_minutes,
             difficulty, priority, planned_date, planned_start, planned_minutes,
             source, ai_meta, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            title,
            subject,
            description,
            due_date,
            estimated,
            difficulty,
            priority,
            planned_date,
            planned_start,
            planned_minutes,
            source or "manual",
            json.dumps(ai_meta, ensure_ascii=False) if ai_meta else None,
            timestamp,
            timestamp,
        ),
    )
    task = query_one("SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,))
    return success(serialize_task(task), status=201, message="任务已创建")


@bp.get("/tasks/history")
def task_history():
    user_id = get_current_user_id()
    limit = query_int("limit", 50, minimum=1, maximum=200)
    rows = query_all(
        """
        SELECT * FROM tasks
        WHERE user_id = ? AND status = 'completed'
        ORDER BY completed_at DESC, id DESC LIMIT ?
        """,
        (user_id, limit),
    )
    return success({"tasks": [serialize_task(row) for row in rows]})


@bp.get("/tasks/<int:task_id>")
def get_task(task_id: int):
    return success(serialize_task(_get_task_or_404(get_current_user_id(), task_id)))


@bp.route("/tasks/<int:task_id>", methods=["PUT", "PATCH"])
def update_task(task_id: int):
    user_id = get_current_user_id()
    existing = _get_task_or_404(user_id, task_id)
    data = json_body()
    fields = {}
    if "title" in data:
        fields["title"] = text_field(data, "title", "任务标题", required=True, max_length=180)
    if "subject" in data:
        fields["subject"] = text_field(data, "subject", "学科", default="综合", max_length=30) or "综合"
    if "description" in data:
        fields["description"] = text_field(data, "description", "任务说明", max_length=3000)
    if "due_date" in data:
        fields["due_date"] = date_field(data, "due_date", "截止日期")
    if "estimated_minutes" in data:
        fields["estimated_minutes"] = int_field(
            data, "estimated_minutes", "预计耗时", minimum=5, maximum=1440
        )
    if "actual_minutes" in data:
        fields["actual_minutes"] = int_field(
            data, "actual_minutes", "实际耗时", default=0, minimum=0, maximum=1440
        )
    if "difficulty" in data:
        fields["difficulty"] = int_field(
            data, "difficulty", "难度", minimum=1, maximum=5
        )
    if "priority" in data:
        fields["priority"] = int_field(
            data, "priority", "优先级", minimum=1, maximum=3
        )
    if "planned_date" in data:
        fields["planned_date"] = date_field(data, "planned_date", "计划日期")
    if "planned_start" in data:
        fields["planned_start"] = time_field(data, "planned_start", "计划开始时间")
    if "planned_minutes" in data:
        fields["planned_minutes"] = int_field(
            data, "planned_minutes", "计划时长", default=None, minimum=1, maximum=1440
        )
    if not fields:
        return success(serialize_task(existing), message="没有需要更新的字段")
    fields["updated_at"] = now_iso()
    assignments = ", ".join(f"{column} = ?" for column in fields)
    execute(
        f"UPDATE tasks SET {assignments} WHERE id = ? AND user_id = ?",
        (*fields.values(), task_id, user_id),
    )
    updated = _get_task_or_404(user_id, task_id)
    return success(serialize_task(updated), message="任务已更新")


@bp.delete("/tasks/<int:task_id>")
def delete_task(task_id: int):
    user_id = get_current_user_id()
    _get_task_or_404(user_id, task_id)
    execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id))
    return success({"deleted_id": task_id}, message="任务已删除")


@bp.post("/tasks/<int:task_id>/complete")
def complete_task(task_id: int):
    user_id = get_current_user_id()
    task = _get_task_or_404(user_id, task_id)
    data = json_body(required=False)
    actual = int_field(
        data,
        "actual_minutes",
        "实际耗时",
        default=task["actual_minutes"] or task["estimated_minutes"],
        minimum=0,
        maximum=1440,
    )
    timestamp = now_iso()
    execute(
        """
        UPDATE tasks SET status = 'completed', actual_minutes = ?, completed_at = ?,
                         updated_at = ?
        WHERE id = ? AND user_id = ?
        """,
        (actual, timestamp, timestamp, task_id, user_id),
    )
    unlocked = evaluate_achievements(user_id)
    updated = _get_task_or_404(user_id, task_id)
    return success(
        {
            "task": serialize_task(updated),
            "unlocked_achievements": unlocked,
        },
        message="任务已完成",
    )


@bp.post("/tasks/<int:task_id>/reopen")
def reopen_task(task_id: int):
    user_id = get_current_user_id()
    _get_task_or_404(user_id, task_id)
    execute(
        """
        UPDATE tasks SET status = 'pending', completed_at = NULL, updated_at = ?
        WHERE id = ? AND user_id = ?
        """,
        (now_iso(), task_id, user_id),
    )
    return success(serialize_task(_get_task_or_404(user_id, task_id)), message="任务已重新打开")


@bp.post("/tasks/<int:task_id>/start")
def start_task(task_id: int):
    user_id = get_current_user_id()
    _get_task_or_404(user_id, task_id)
    execute(
        """
        UPDATE tasks SET status = 'in_progress', updated_at = ?
        WHERE id = ? AND user_id = ? AND status = 'pending'
        """,
        (now_iso(), task_id, user_id),
    )
    return success(serialize_task(_get_task_or_404(user_id, task_id)), message="任务已开始")


def _validate_plan_request(data: dict) -> dict:
    available_minutes = int_field(
        data,
        "available_minutes",
        "可用时间",
        default=120,
        required=False,
        minimum=10,
        maximum=720,
    )
    start_time = time_field(data, "start_time", "开始时间", default="19:00") or "19:00"
    plan_date = date_field(data, "plan_date", "计划日期", default=today_iso()) or today_iso()
    task_ids = data.get("task_ids")
    if task_ids is not None:
        if not isinstance(task_ids, list):
            from ..utils.exceptions import APIError

            raise APIError(
                "task_ids 必须是任务 ID 数组", code="VALIDATION_ERROR", status_code=400
            )
        cleaned = []
        for item in task_ids[:100]:
            try:
                cleaned.append(int(item))
            except (TypeError, ValueError):
                continue
        task_ids = cleaned
    return {
        "available_minutes": available_minutes,
        "start_time": start_time,
        "plan_date": plan_date,
        "task_ids": task_ids or None,
    }


@bp.post("/tasks/plan")
@bp.post("/tasks/plan/preview")
def plan_preview():
    data = _validate_plan_request(json_body())
    plan = build_plan(
        get_current_user_id(),
        available_minutes=data["available_minutes"],
        start_time=data["start_time"],
        plan_date=data["plan_date"],
        task_ids=data["task_ids"],
    )
    return success(plan)


@bp.post("/tasks/plan/apply")
def plan_apply():
    user_id = get_current_user_id()
    data = json_body()
    plan_date = date_field(data, "plan_date", "计划日期", default=today_iso()) or today_iso()
    schedule = data.get("schedule")
    if not isinstance(schedule, list) or not schedule:
        from ..utils.exceptions import APIError

        raise APIError(
            "schedule 必须是非空数组", code="VALIDATION_ERROR", status_code=400
        )
    validated = []
    for item in schedule[:100]:
        if not isinstance(item, dict):
            continue
        try:
            task_id = int(item.get("task_id"))
            planned_minutes = int(item.get("planned_minutes"))
        except (TypeError, ValueError):
            continue
        start_time = item.get("start_time")
        try:
            start_time = time_field({"start_time": start_time}, "start_time", "开始时间")
        except Exception:
            start_time = None
        if planned_minutes > 0:
            validated.append(
                {
                    "task_id": task_id,
                    "start_time": start_time,
                    "planned_minutes": min(planned_minutes, 1440),
                }
            )
    if not validated:
        from ..utils.exceptions import APIError

        raise APIError("没有可应用的有效排期", code="VALIDATION_ERROR", status_code=400)
    count = apply_plan(user_id, validated, plan_date)
    tasks = query_all(
        "SELECT * FROM tasks WHERE user_id = ? AND planned_date = ? ORDER BY planned_start",
        (user_id, plan_date),
    )
    return success(
        {
            "applied_count": count,
            "plan_date": plan_date,
            "tasks": [serialize_task(row) for row in tasks],
        },
        message=f"已应用 {count} 个任务的排期",
    )
