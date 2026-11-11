"""Wrong-question notebook with knowledge-point tagging."""

from __future__ import annotations

import json

from flask import Blueprint, request

from ..db import execute, get_current_user_id, query_all, query_one
from ..utils.exceptions import APIError, NotFound
from ..utils.responses import success
from ..utils.serializers import serialize_error_record
from ..utils.timeutils import now_iso
from ..utils.validators import query_int, text_field, json_body

bp = Blueprint("error_records", __name__)
MASTERY_LEVELS = {"new", "reviewing", "mastered"}


def _get_error_or_404(user_id: int, error_id: int):
    row = query_one(
        "SELECT * FROM error_records WHERE id = ? AND user_id = ?",
        (error_id, user_id),
    )
    if not row:
        raise NotFound("错题记录不存在或已被删除")
    return row


def _knowledge_points(data: dict) -> str:
    value = data.get("knowledge_points", [])
    if isinstance(value, str):
        points = [part.strip() for part in value.replace("，", ",").split(",")]
    elif isinstance(value, list):
        points = [str(part).strip() for part in value]
    else:
        points = []
    cleaned = []
    for point in points:
        if point and point not in cleaned:
            cleaned.append(point[:80])
    return json.dumps(cleaned[:12], ensure_ascii=False)


def _validate_mastery(raw) -> str:
    value = raw if raw in MASTERY_LEVELS else "new"
    return value


@bp.get("/errors")
def list_errors():
    user_id = get_current_user_id()
    subject = (request.args.get("subject") or "").strip()
    mastery = (request.args.get("mastery") or "").strip()
    search = (request.args.get("q") or "").strip()
    limit = query_int("limit", 100, minimum=1, maximum=300)
    conditions = ["user_id = ?"]
    params: list = [user_id]
    if subject and subject != "all":
        conditions.append("subject = ?")
        params.append(subject)
    if mastery in MASTERY_LEVELS:
        conditions.append("mastery = ?")
        params.append(mastery)
    if search:
        conditions.append("(question LIKE ? OR knowledge_points LIKE ? OR analysis LIKE ?)")
        params.extend([f"%{search}%"] * 3)
    rows = query_all(
        f"""
        SELECT * FROM error_records WHERE {' AND '.join(conditions)}
        ORDER BY
          CASE mastery WHEN 'new' THEN 0 WHEN 'reviewing' THEN 1 ELSE 2 END,
          updated_at DESC, id DESC LIMIT ?
        """,
        (*params, limit),
    )
    subject_rows = query_all(
        "SELECT DISTINCT subject FROM error_records WHERE user_id = ? ORDER BY subject",
        (user_id,),
    )
    counts = query_one(
        """
        SELECT COUNT(*) AS total,
          SUM(CASE WHEN mastery = 'new' THEN 1 ELSE 0 END) AS new,
          SUM(CASE WHEN mastery = 'reviewing' THEN 1 ELSE 0 END) AS reviewing,
          SUM(CASE WHEN mastery = 'mastered' THEN 1 ELSE 0 END) AS mastered
        FROM error_records WHERE user_id = ?
        """,
        (user_id,),
    )
    return success(
        {
            "errors": [serialize_error_record(row) for row in rows],
            "counts": dict(counts) if counts else {},
            "subjects": [row["subject"] for row in subject_rows],
            "filters": {"subject": subject or "all", "mastery": mastery or "all", "q": search},
        }
    )


@bp.post("/errors")
def create_error():
    user_id = get_current_user_id()
    data = json_body()
    subject = text_field(data, "subject", "学科", required=True, max_length=30)
    question = text_field(data, "question", "题目", required=True, max_length=10000)
    student_answer = text_field(data, "student_answer", "学生答案", max_length=10000)
    correct_answer = text_field(data, "correct_answer", "正确答案", max_length=10000)
    analysis = text_field(data, "analysis", "错因分析", max_length=10000)
    mastery = _validate_mastery(data.get("mastery"))
    source = text_field(data, "source", "来源", default="manual", max_length=50)
    timestamp = now_iso()
    cursor = execute(
        """
        INSERT INTO error_records
            (user_id, subject, question, student_answer, correct_answer,
             analysis, knowledge_points, mastery, source, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            subject,
            question,
            student_answer,
            correct_answer,
            analysis,
            _knowledge_points(data),
            mastery,
            source or "manual",
            timestamp,
            timestamp,
        ),
    )
    row = _get_error_or_404(user_id, cursor.lastrowid)
    return success(serialize_error_record(row), status=201, message="错题已保存")


@bp.route("/errors/<int:error_id>", methods=["PUT", "PATCH"])
def update_error(error_id: int):
    user_id = get_current_user_id()
    existing = _get_error_or_404(user_id, error_id)
    data = json_body()
    fields = {}
    for field, label, max_length in (
        ("subject", "学科", 30),
        ("question", "题目", 10000),
        ("student_answer", "学生答案", 10000),
        ("correct_answer", "正确答案", 10000),
        ("analysis", "错因分析", 10000),
        ("source", "来源", 50),
    ):
        if field in data:
            required = field in {"subject", "question"}
            fields[field] = text_field(
                data, field, label, required=required, max_length=max_length
            )
    if "knowledge_points" in data:
        fields["knowledge_points"] = _knowledge_points(data)
    if "mastery" in data:
        fields["mastery"] = _validate_mastery(data.get("mastery"))
    if not fields:
        return success(serialize_error_record(existing), message="没有需要更新的字段")
    fields["updated_at"] = now_iso()
    assignments = ", ".join(f"{column} = ?" for column in fields)
    execute(
        f"UPDATE error_records SET {assignments} WHERE id = ? AND user_id = ?",
        (*fields.values(), error_id, user_id),
    )
    return success(
        serialize_error_record(_get_error_or_404(user_id, error_id)),
        message="错题已更新",
    )


@bp.delete("/errors/<int:error_id>")
def delete_error(error_id: int):
    user_id = get_current_user_id()
    _get_error_or_404(user_id, error_id)
    execute(
        "DELETE FROM error_records WHERE id = ? AND user_id = ?", (error_id, user_id)
    )
    return success({"deleted_id": error_id}, message="错题已删除")
