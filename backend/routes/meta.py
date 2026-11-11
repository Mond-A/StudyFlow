"""Health, app metadata, user settings, demo data and export endpoints."""

from __future__ import annotations

import json
import re
from datetime import datetime

from flask import Blueprint, Response

from ..config import Config
from ..db import (
    execute,
    get_current_user,
    get_current_user_id,
    query_all,
    query_one,
)
from ..services.ai_service import AIService
from ..services.constants import SUBJECTS
from ..services.demo_data import clear_demo_data, demo_summary, seed_demo_data
from ..utils.exceptions import APIError
from ..utils.responses import success
from ..utils.serializers import (
    serialize_error_record,
    serialize_flashcard,
    serialize_grade,
    serialize_note,
    serialize_session,
    serialize_task,
    serialize_user,
)
from ..utils.timeutils import now_iso, now_local
from ..utils.validators import int_field, json_body, text_field

bp = Blueprint("meta", __name__)


@bp.get("/health")
def health():
    query_one("SELECT 1 AS ok")
    return success(
        {
            "status": "ok",
            "app": Config.APP_NAME,
            "version": Config.APP_VERSION,
            "server_time": now_iso(),
        }
    )


@bp.get("/meta")
def app_meta():
    user = get_current_user()
    ai_status = AIService.from_app().status()
    return success(
        {
            "app": {
                "name": Config.APP_NAME,
                "version": Config.APP_VERSION,
                "tagline": "AI 学习管理工作台",
            },
            "server_time": now_iso(),
            "user": serialize_user(user),
            "subjects": SUBJECTS,
            "ai": ai_status,
            "demo": demo_summary(),
            "limits": {
                "max_image_mb": 8,
                "supported_image_types": ["JPG", "PNG", "WebP"],
                "notes_max_chars": 200000,
            },
        }
    )


@bp.get("/settings")
def get_settings():
    user = get_current_user()
    return success(
        {
            "user": serialize_user(user),
            "ai": AIService.from_app().status(),
            "demo": demo_summary(),
            "subjects": SUBJECTS,
        }
    )


@bp.put("/settings")
@bp.patch("/settings")
def update_settings():
    user_id = get_current_user_id()
    data = json_body()
    fields = {}
    if "display_name" in data:
        display = text_field(
            data, "display_name", "昵称", required=True, max_length=40
        )
        fields["display_name"] = display
    if "email" in data:
        email = text_field(data, "email", "邮箱", max_length=120)
        if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise APIError("邮箱格式不正确", code="VALIDATION_ERROR", status_code=400)
        fields["email"] = email or None
    if "avatar_color" in data:
        color = text_field(data, "avatar_color", "头像颜色", max_length=7)
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            raise APIError(
                "头像颜色必须是 #RRGGBB 格式",
                code="VALIDATION_ERROR",
                status_code=400,
            )
        fields["avatar_color"] = color.lower()
    for field, label, minimum, maximum in (
        ("daily_goal_minutes", "每日学习目标", 15, 720),
        ("pomodoro_minutes", "番茄钟时长", 1, 120),
        ("short_break_minutes", "短休息时长", 1, 60),
        ("long_break_minutes", "长休息时长", 1, 120),
    ):
        if field in data:
            fields[field] = int_field(
                data,
                field,
                label,
                required=True,
                minimum=minimum,
                maximum=maximum,
            )
    if not fields:
        return success(
            {"user": serialize_user(get_current_user())},
            message="没有需要更新的设置",
        )
    fields["updated_at"] = now_iso()
    assignments = ", ".join(f"{column} = ?" for column in fields)
    execute(
        f"UPDATE users SET {assignments} WHERE id = ?",
        (*fields.values(), user_id),
    )
    user = query_one("SELECT * FROM users WHERE id = ?", (user_id,))
    return success({"user": serialize_user(user)}, message="设置已保存")


@bp.get("/demo")
def get_demo():
    return success(demo_summary())


@bp.post("/demo/load")
def load_demo():
    result = seed_demo_data(force=True)
    return success(result, status=200, message=result.get("message", "演示数据已处理"))


@bp.delete("/demo/clear")
def clear_demo():
    result = clear_demo_data()
    return success(result, message=result.get("message", "演示数据已清除"))


def _rows(sql: str, user_id: int) -> list:
    return [dict(row) for row in query_all(sql, (user_id,))]


@bp.get("/export")
def export_data():
    """Download a full JSON backup of this user's StudyFlow data."""
    user_id = get_current_user_id()
    user = get_current_user()
    payload = {
        "exported_at": now_iso(),
        "app": {"name": Config.APP_NAME, "version": Config.APP_VERSION},
        "user": serialize_user(user),
        "subjects": SUBJECTS,
        "tasks": [
            serialize_task(row)
            for row in query_all("SELECT * FROM tasks WHERE user_id = ?", (user_id,))
        ],
        "grades": [
            serialize_grade(row)
            for row in query_all("SELECT * FROM grades WHERE user_id = ?", (user_id,))
        ],
        "notes": [
            serialize_note(row)
            for row in query_all("SELECT * FROM notes WHERE user_id = ?", (user_id,))
        ],
        "study_sessions": [
            serialize_session(row)
            for row in query_all(
                """
                SELECT s.*, t.title AS task_title FROM study_sessions s
                LEFT JOIN tasks t ON t.id = s.task_id
                WHERE s.user_id = ? ORDER BY s.started_at
                """,
                (user_id,),
            )
        ],
        "achievements": _rows(
            "SELECT * FROM achievements WHERE user_id = ? ORDER BY unlocked_at",
            user_id,
        ),
        "error_records": [
            serialize_error_record(row)
            for row in query_all(
                "SELECT * FROM error_records WHERE user_id = ?", (user_id,)
            )
        ],
        "flashcards": [
            serialize_flashcard(row)
            for row in query_all("SELECT * FROM flashcards WHERE user_id = ?", (user_id,))
        ],
        "demo": demo_summary(),
    }
    filename = f"studyflow-export-{now_local().strftime('%Y%m%d-%H%M%S')}.json"
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    response = Response(body, mimetype="application/json")
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
