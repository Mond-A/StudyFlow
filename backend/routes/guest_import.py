"""Explicit guest-data import into the authenticated account.

Guest data lives only in the browser. This endpoint is called only after the
user confirms the import. It never accepts a target user_id from the client,
never overwrites existing account rows, and is idempotent per user/batch and
per local record UID.
"""

from __future__ import annotations

import json
import re
import uuid

from flask import Blueprint, request

from ..db import execute, get_current_user_id, query_one, transaction
from ..services.achievements import evaluate_achievements
from ..utils.exceptions import APIError
from ..utils.responses import success
from ..utils.timeutils import now_iso
from ..utils.validators import json_body

bp = Blueprint("guest_import", __name__)

ENTITIES = ("tasks", "grades", "notes", "study_sessions", "flashcards", "errors")
UID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,80}$")


def _uid(value) -> str:
    uid = str(value or "").strip()
    if not UID_RE.fullmatch(uid):
        raise APIError("访客记录标识无效", code="INVALID_GUEST_RECORD", status_code=400)
    return uid


def _text(value, field: str, *, required: bool = False, max_length: int = 10000, default: str = "") -> str:
    text = str(value or "").strip()
    if required and not text:
        raise APIError(f"{field}不能为空", code="VALIDATION_ERROR", status_code=400)
    if len(text) > max_length:
        raise APIError(f"{field}过长", code="VALIDATION_ERROR", status_code=400)
    return text or default


def _number(value, field: str, *, minimum=0, maximum=100000, default=0):
    if value in (None, "") and default is None:
        return None
    try:
        number = float(value if value not in (None, "") else default)
    except (TypeError, ValueError) as exc:
        raise APIError(f"{field}格式无效", code="VALIDATION_ERROR", status_code=400) from exc
    if number < minimum or number > maximum:
        raise APIError(f"{field}超出范围", code="VALIDATION_ERROR", status_code=400)
    return number


def _date(value, field: str, *, required: bool = False):
    text = _text(value, field, required=required, max_length=10)
    if not text:
        return None
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        raise APIError(f"{field}格式应为 YYYY-MM-DD", code="VALIDATION_ERROR", status_code=400)
    return text


def _records(payload: dict, key: str) -> list[dict]:
    value = payload.get(key, [])
    if not isinstance(value, list):
        raise APIError(f"{key}必须是数组", code="VALIDATION_ERROR", status_code=400)
    if len(value) > 2000:
        raise APIError("单次导入记录过多", code="IMPORT_TOO_LARGE", status_code=413)
    if any(not isinstance(item, dict) for item in value):
        raise APIError(f"{key}包含无效记录", code="VALIDATION_ERROR", status_code=400)
    return value


def _existing_item(db, user_id: int, entity: str, uid: str):
    return db.execute(
        "SELECT server_id FROM guest_import_items WHERE user_id = ? AND entity = ? AND local_uid = ?",
        (user_id, entity, uid),
    ).fetchone()


def _remember(db, user_id: int, batch_id: int, entity: str, uid: str, server_id: int) -> None:
    db.execute(
        """
        INSERT INTO guest_import_items
            (user_id, batch_id, entity, local_uid, server_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, batch_id, entity, uid, server_id, now_iso()),
    )


def _import_tasks(db, user_id: int, batch_id: int, rows: list[dict], counts: dict) -> dict[str, int]:
    mapping = {}
    for row in rows:
        uid = _uid(row.get("local_uid"))
        existing = _existing_item(db, user_id, "tasks", uid)
        if existing:
            mapping[uid] = int(existing["server_id"])
            counts["tasks"]["skipped"] += 1
            continue
        title = _text(row.get("title"), "任务标题", required=True, max_length=180)
        timestamp = _text(row.get("created_at"), "创建时间", max_length=40, default=now_iso()) or now_iso()
        cursor = db.execute(
            """
            INSERT INTO tasks
                (user_id, title, subject, description, due_date, estimated_minutes,
                 actual_minutes, difficulty, status, priority, planned_date,
                 planned_start, planned_minutes, source, completed_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'import', ?, ?, ?)
            """,
            (
                user_id,
                title,
                _text(row.get("subject"), "学科", max_length=30, default="综合") or "综合",
                _text(row.get("description"), "说明", max_length=1000),
                _date(row.get("due_date"), "截止日期"),
                int(_number(row.get("estimated_minutes"), "预计时长", minimum=1, maximum=1440, default=30)),
                int(_number(row.get("actual_minutes"), "实际时长", minimum=0, maximum=1440, default=0)),
                int(_number(row.get("difficulty"), "难度", minimum=1, maximum=5, default=3)),
                _text(row.get("status"), "状态", max_length=20, default="pending") or "pending",
                int(_number(row.get("priority"), "优先级", minimum=1, maximum=3, default=2)),
                _date(row.get("planned_date"), "计划日期"),
                _text(row.get("planned_start"), "计划开始", max_length=5) or None,
                _number(row.get("planned_minutes"), "计划时长", minimum=1, maximum=1440, default=None),
                _text(row.get("completed_at"), "完成时间", max_length=40) or None,
                timestamp,
                _text(row.get("updated_at"), "更新时间", max_length=40, default=timestamp) or timestamp,
            ),
        )
        mapping[uid] = int(cursor.lastrowid)
        _remember(db, user_id, batch_id, "tasks", uid, int(cursor.lastrowid))
        counts["tasks"]["imported"] += 1
    return mapping


def _import_grades(db, user_id: int, batch_id: int, rows: list[dict], counts: dict) -> None:
    for row in rows:
        uid = _uid(row.get("local_uid"))
        if _existing_item(db, user_id, "grades", uid):
            counts["grades"]["skipped"] += 1
            continue
        timestamp = _text(row.get("created_at"), "创建时间", max_length=40, default=now_iso()) or now_iso()
        cursor = db.execute(
            """
            INSERT INTO grades
                (user_id, subject, exam_name, score, max_score, exam_date, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                _text(row.get("subject"), "学科", required=True, max_length=30),
                _text(row.get("exam_name"), "考试名称", required=True, max_length=120),
                _number(row.get("score"), "分数"),
                _number(row.get("max_score"), "满分", minimum=0.01, maximum=100000, default=100),
                _date(row.get("exam_date"), "考试日期", required=True),
                _text(row.get("notes"), "备注", max_length=1000),
                timestamp,
                _text(row.get("updated_at"), "更新时间", max_length=40, default=timestamp) or timestamp,
            ),
        )
        _remember(db, user_id, batch_id, "grades", uid, int(cursor.lastrowid))
        counts["grades"]["imported"] += 1


def _import_notes(db, user_id: int, batch_id: int, rows: list[dict], counts: dict) -> dict[str, int]:
    mapping = {}
    for row in rows:
        uid = _uid(row.get("local_uid"))
        existing = _existing_item(db, user_id, "notes", uid)
        if existing:
            mapping[uid] = int(existing["server_id"])
            counts["notes"]["skipped"] += 1
            continue
        timestamp = _text(row.get("created_at"), "创建时间", max_length=40, default=now_iso()) or now_iso()
        cursor = db.execute(
            """
            INSERT INTO notes
                (user_id, title, subject, content_markdown, source_image, created_at, updated_at)
            VALUES (?, ?, ?, ?, NULL, ?, ?)
            """,
            (
                user_id,
                _text(row.get("title"), "笔记标题", required=True, max_length=180),
                _text(row.get("subject"), "学科", max_length=30, default="综合") or "综合",
                _text(row.get("content_markdown"), "笔记内容", max_length=200000),
                timestamp,
                _text(row.get("updated_at"), "更新时间", max_length=40, default=timestamp) or timestamp,
            ),
        )
        mapping[uid] = int(cursor.lastrowid)
        _remember(db, user_id, batch_id, "notes", uid, int(cursor.lastrowid))
        counts["notes"]["imported"] += 1
    return mapping


def _import_sessions(
    db, user_id: int, batch_id: int, rows: list[dict], task_map: dict, counts: dict
) -> None:
    for row in rows:
        uid = _uid(row.get("local_uid"))
        if _existing_item(db, user_id, "study_sessions", uid):
            counts["study_sessions"]["skipped"] += 1
            continue
        task_uid = str(row.get("local_task_uid") or "").strip()
        task_id = None
        if task_uid:
            task_id = task_map.get(task_uid)
            if task_id is None:
                raise APIError("学习记录关联的访客任务不存在", code="INVALID_REFERENCE", status_code=400)
        timestamp = _text(row.get("created_at"), "创建时间", max_length=40, default=now_iso()) or now_iso()
        cursor = db.execute(
            """
            INSERT INTO study_sessions
                (user_id, task_id, subject, duration_minutes, session_type,
                 started_at, ended_at, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                task_id,
                _text(row.get("subject"), "学科", max_length=30, default="综合") or "综合",
                int(_number(row.get("duration_minutes"), "学习时长", minimum=1, maximum=1440, default=25)),
                _text(row.get("session_type"), "记录类型", max_length=20, default="pomodoro") or "pomodoro",
                _text(row.get("started_at"), "开始时间", required=True, max_length=40),
                _text(row.get("ended_at"), "结束时间", max_length=40) or None,
                _text(row.get("note"), "备注", max_length=1000),
                timestamp,
            ),
        )
        _remember(db, user_id, batch_id, "study_sessions", uid, int(cursor.lastrowid))
        counts["study_sessions"]["imported"] += 1


def _import_flashcards(db, user_id: int, batch_id: int, rows: list[dict], note_map: dict, counts: dict) -> None:
    for row in rows:
        uid = _uid(row.get("local_uid"))
        if _existing_item(db, user_id, "flashcards", uid):
            counts["flashcards"]["skipped"] += 1
            continue
        note_uid = str(row.get("local_note_uid") or "").strip()
        note_id = None
        if note_uid:
            note_id = note_map.get(note_uid)
            if note_id is None:
                raise APIError("闪卡关联的访客笔记不存在", code="INVALID_REFERENCE", status_code=400)
        timestamp = _text(row.get("created_at"), "创建时间", max_length=40, default=now_iso()) or now_iso()
        cursor = db.execute(
            """
            INSERT INTO flashcards
                (user_id, note_id, front, back, subject, mastery_level,
                 review_count, next_review_date, last_reviewed_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                note_id,
                _text(row.get("front"), "卡片正面", required=True, max_length=10000),
                _text(row.get("back"), "卡片背面", required=True, max_length=10000),
                _text(row.get("subject"), "学科", max_length=30, default="综合") or "综合",
                int(_number(row.get("mastery_level"), "掌握程度", minimum=0, maximum=5, default=0)),
                int(_number(row.get("review_count"), "复习次数", minimum=0, maximum=100000, default=0)),
                _date(row.get("next_review_date"), "下次复习日期"),
                _text(row.get("last_reviewed_at"), "最后复习时间", max_length=40) or None,
                timestamp,
                _text(row.get("updated_at"), "更新时间", max_length=40, default=timestamp) or timestamp,
            ),
        )
        _remember(db, user_id, batch_id, "flashcards", uid, int(cursor.lastrowid))
        counts["flashcards"]["imported"] += 1


def _import_errors(db, user_id: int, batch_id: int, rows: list[dict], counts: dict) -> None:
    for row in rows:
        uid = _uid(row.get("local_uid"))
        if _existing_item(db, user_id, "errors", uid):
            counts["errors"]["skipped"] += 1
            continue
        knowledge = row.get("knowledge_points", [])
        if not isinstance(knowledge, list):
            knowledge = []
        timestamp = _text(row.get("created_at"), "创建时间", max_length=40, default=now_iso()) or now_iso()
        cursor = db.execute(
            """
            INSERT INTO error_records
                (user_id, subject, question, student_answer, correct_answer,
                 analysis, knowledge_points, mastery, source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'guest_import', ?, ?)
            """,
            (
                user_id,
                _text(row.get("subject"), "学科", required=True, max_length=30),
                _text(row.get("question"), "题目", required=True, max_length=10000),
                _text(row.get("student_answer"), "学生答案", max_length=10000),
                _text(row.get("correct_answer"), "正确答案", max_length=10000),
                _text(row.get("analysis"), "错因分析", max_length=10000),
                json.dumps([str(item)[:100] for item in knowledge[:30]], ensure_ascii=False),
                _text(row.get("mastery"), "掌握状态", max_length=20, default="new") or "new",
                timestamp,
                _text(row.get("updated_at"), "更新时间", max_length=40, default=timestamp) or timestamp,
            ),
        )
        _remember(db, user_id, batch_id, "errors", uid, int(cursor.lastrowid))
        counts["errors"]["imported"] += 1


@bp.post("/guest/import")
def import_guest_data():
    user_id = get_current_user_id()
    payload = json_body()
    batch_id_value = str(payload.get("client_batch_id") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9._:-]{1,80}", batch_id_value):
        raise APIError("导入批次标识无效", code="VALIDATION_ERROR", status_code=400)
    data = payload.get("data")
    if not isinstance(data, dict):
        raise APIError("访客数据格式无效", code="VALIDATION_ERROR", status_code=400)
    device_id = _text(payload.get("device_id"), "设备标识", max_length=120)

    existing_batch = query_one(
        "SELECT summary_json FROM guest_import_batches WHERE user_id = ? AND client_batch_id = ?",
        (user_id, batch_id_value),
    )
    if existing_batch:
        return success(
            {**json.loads(existing_batch["summary_json"]), "already_imported": True},
            message="该访客数据批次已经导入。",
        )

    rows = {entity: _records(data, entity) for entity in ENTITIES}
    if not any(rows.values()):
        raise APIError("没有可导入的访客数据", code="EMPTY_IMPORT", status_code=400)

    counts = {entity: {"imported": 0, "skipped": 0} for entity in ENTITIES}
    try:
        with transaction() as db:
            cursor = db.execute(
                """
                INSERT INTO guest_import_batches
                    (user_id, client_batch_id, device_id, summary_json, created_at)
                VALUES (?, ?, ?, '{}', ?)
                """,
                (user_id, batch_id_value, device_id, now_iso()),
            )
            batch_id = int(cursor.lastrowid)
            task_map = _import_tasks(db, user_id, batch_id, rows["tasks"], counts)
            _import_grades(db, user_id, batch_id, rows["grades"], counts)
            note_map = _import_notes(db, user_id, batch_id, rows["notes"], counts)
            _import_sessions(db, user_id, batch_id, rows["study_sessions"], task_map, counts)
            _import_flashcards(db, user_id, batch_id, rows["flashcards"], note_map, counts)
            _import_errors(db, user_id, batch_id, rows["errors"], counts)
            evaluate_achievements(user_id)
            summary = {
                "batch_id": batch_id_value,
                "counts": counts,
                "total_imported": sum(item["imported"] for item in counts.values()),
                "total_skipped": sum(item["skipped"] for item in counts.values()),
                "achievements_recomputed": True,
            }
            db.execute(
                "UPDATE guest_import_batches SET summary_json = ? WHERE id = ?",
                (json.dumps(summary, ensure_ascii=False), batch_id),
            )
    except Exception:
        # The transaction helper rolls back the batch and every inserted row.
        raise

    return success(summary, message="访客数据已导入当前账户，本地访客数据仍然保留。")
