"""Grade CRUD and analytics endpoints."""

from __future__ import annotations

from flask import Blueprint, request

from ..db import execute, get_current_user_id, query_all, query_one
from ..services.achievements import evaluate_achievements
from ..services.analytics import grade_analytics
from ..utils.exceptions import APIError, NotFound
from ..utils.responses import success
from ..utils.serializers import serialize_grade
from ..utils.timeutils import now_iso, today_iso
from ..utils.validators import (
    date_field,
    float_field,
    json_body,
    query_int,
    text_field,
)

bp = Blueprint("grades", __name__)


def _get_grade_or_404(user_id: int, grade_id: int):
    row = query_one(
        "SELECT * FROM grades WHERE id = ? AND user_id = ?", (grade_id, user_id)
    )
    if not row:
        raise NotFound("成绩记录不存在或已被删除")
    return row


@bp.get("/grades")
def list_grades():
    user_id = get_current_user_id()
    subject = (request.args.get("subject") or "").strip()
    range_value = (request.args.get("range") or "90").strip()
    analytics = grade_analytics(user_id, subject=subject or None, range_value=range_value)
    return success(
        {
            "grades": analytics["records"],
            "analytics": analytics,
            "subjects": analytics["available_subjects"],
        }
    )


@bp.get("/grades/analytics")
def grades_analytics():
    user_id = get_current_user_id()
    subject = (request.args.get("subject") or "").strip()
    range_value = (request.args.get("range") or "90").strip()
    return success(
        grade_analytics(user_id, subject=subject or None, range_value=range_value)
    )


@bp.post("/grades")
def create_grade():
    user_id = get_current_user_id()
    data = json_body()
    subject = text_field(data, "subject", "学科", required=True, max_length=30)
    exam_name = text_field(data, "exam_name", "考试名称", required=True, max_length=120)
    score = float_field(data, "score", "分数", required=True, minimum=0, maximum=100000)
    max_score = float_field(
        data, "max_score", "满分", default=100.0, minimum=0.1, maximum=100000
    )
    if score is None or max_score is None:
        raise APIError("请输入分数和满分", code="VALIDATION_ERROR", status_code=400)
    if score > max_score:
        raise APIError(
            "分数不能大于满分", code="VALIDATION_ERROR", status_code=400
        )
    exam_date = date_field(
        data, "exam_date", "考试日期", required=True, default=today_iso()
    )
    notes = text_field(data, "notes", "备注", max_length=2000)
    timestamp = now_iso()
    cursor = execute(
        """
        INSERT INTO grades
            (user_id, subject, exam_name, score, max_score, exam_date, notes,
             created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            subject,
            exam_name,
            score,
            max_score,
            exam_date,
            notes,
            timestamp,
            timestamp,
        ),
    )
    evaluate_achievements(user_id)
    row = _get_grade_or_404(user_id, cursor.lastrowid)
    return success(serialize_grade(row), status=201, message="成绩已保存")


@bp.route("/grades/<int:grade_id>", methods=["PUT", "PATCH"])
def update_grade(grade_id: int):
    user_id = get_current_user_id()
    existing = _get_grade_or_404(user_id, grade_id)
    data = json_body()
    fields = {}
    if "subject" in data:
        fields["subject"] = text_field(data, "subject", "学科", required=True, max_length=30)
    if "exam_name" in data:
        fields["exam_name"] = text_field(
            data, "exam_name", "考试名称", required=True, max_length=120
        )
    if "score" in data:
        fields["score"] = float_field(data, "score", "分数", minimum=0, maximum=100000)
    if "max_score" in data:
        fields["max_score"] = float_field(
            data, "max_score", "满分", minimum=0.1, maximum=100000
        )
    if "exam_date" in data:
        fields["exam_date"] = date_field(data, "exam_date", "考试日期", required=True)
    if "notes" in data:
        fields["notes"] = text_field(data, "notes", "备注", max_length=2000)
    final_score = fields.get("score", existing["score"])
    final_max = fields.get("max_score", existing["max_score"])
    if final_score > final_max:
        raise APIError("分数不能大于满分", code="VALIDATION_ERROR", status_code=400)
    if not fields:
        return success(serialize_grade(existing), message="没有需要更新的字段")
    fields["updated_at"] = now_iso()
    assignments = ", ".join(f"{column} = ?" for column in fields)
    execute(
        f"UPDATE grades SET {assignments} WHERE id = ? AND user_id = ?",
        (*fields.values(), grade_id, user_id),
    )
    return success(
        serialize_grade(_get_grade_or_404(user_id, grade_id)), message="成绩已更新"
    )


@bp.delete("/grades/<int:grade_id>")
def delete_grade(grade_id: int):
    user_id = get_current_user_id()
    _get_grade_or_404(user_id, grade_id)
    execute("DELETE FROM grades WHERE id = ? AND user_id = ?", (grade_id, user_id))
    return success({"deleted_id": grade_id}, message="成绩记录已删除")
