"""Notes CRUD plus AI audit and knowledge-graph endpoints."""

from __future__ import annotations

import json
import re

from flask import Blueprint, request

from ..db import execute, get_current_user_id, query_all, query_one
from ..services.achievements import evaluate_achievements
from ..services.ai_features import AIFeatures
from ..utils.exceptions import APIError, NotFound
from ..utils.responses import success
from ..utils.serializers import serialize_note, serialize_note_summary
from ..utils.timeutils import now_iso
from ..utils.validators import bool_field, json_body, query_int, text_field

bp = Blueprint("notes", __name__)


def _get_note_or_404(user_id: int, note_id: int):
    row = query_one(
        "SELECT * FROM notes WHERE id = ? AND user_id = ?", (note_id, user_id)
    )
    if not row:
        raise NotFound("笔记不存在或已被删除")
    return row


def _source_image_value(value: str, user_id: int) -> str | None:
    """Allow only a local upload URL owned by the current account."""
    if not value:
        return None
    if not re.fullmatch(r"/uploads/[a-f0-9]{32}\.(?:jpg|png|webp)", value):
        raise APIError(
            "来源图片必须是本地上传接口返回的 /uploads/ 地址",
            code="INVALID_SOURCE_IMAGE",
            status_code=400,
        )
    filename = value.removeprefix("/uploads/")
    owned = query_one(
        "SELECT 1 FROM uploads WHERE stored_filename = ? AND user_id = ?",
        (filename, user_id),
    )
    if owned is None:
        raise APIError(
            "来源图片不存在或无权访问",
            code="UPLOAD_NOT_FOUND",
            status_code=404,
        )
    return value


@bp.get("/notes")
def list_notes():
    user_id = get_current_user_id()
    subject = (request.args.get("subject") or "").strip()
    search = (request.args.get("q") or "").strip()
    limit = query_int("limit", 100, minimum=1, maximum=300)
    conditions = ["user_id = ?"]
    params: list = [user_id]
    if subject and subject != "all":
        conditions.append("subject = ?")
        params.append(subject)
    if search:
        conditions.append("(title LIKE ? OR content_markdown LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    rows = query_all(
        f"""
        SELECT * FROM notes WHERE {' AND '.join(conditions)}
        ORDER BY updated_at DESC, id DESC LIMIT ?
        """,
        (*params, limit),
    )
    subject_rows = query_all(
        "SELECT DISTINCT subject FROM notes WHERE user_id = ? ORDER BY subject",
        (user_id,),
    )
    return success(
        {
            "notes": [serialize_note_summary(row) for row in rows],
            "subjects": [row["subject"] for row in subject_rows],
            "filters": {"subject": subject or "all", "q": search},
        }
    )


@bp.post("/notes")
def create_note():
    user_id = get_current_user_id()
    data = json_body()
    title = text_field(data, "title", "笔记标题", required=True, max_length=180)
    subject = text_field(data, "subject", "学科", default="综合", max_length=30) or "综合"
    content = text_field(data, "content_markdown", "笔记内容", max_length=200000)
    source_image = _source_image_value(
        text_field(data, "source_image", "来源图片", max_length=500), user_id
    )
    timestamp = now_iso()
    cursor = execute(
        """
        INSERT INTO notes
            (user_id, title, subject, content_markdown, source_image,
             created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, title, subject, content, source_image, timestamp, timestamp),
    )
    evaluate_achievements(user_id)
    row = _get_note_or_404(user_id, cursor.lastrowid)
    return success(serialize_note(row), status=201, message="笔记已保存")


@bp.get("/notes/<int:note_id>")
def get_note(note_id: int):
    row = _get_note_or_404(get_current_user_id(), note_id)
    return success(serialize_note(row))


@bp.route("/notes/<int:note_id>", methods=["PUT", "PATCH"])
def update_note(note_id: int):
    user_id = get_current_user_id()
    existing = _get_note_or_404(user_id, note_id)
    data = json_body()
    fields = {}
    if "title" in data:
        fields["title"] = text_field(data, "title", "笔记标题", required=True, max_length=180)
    if "subject" in data:
        fields["subject"] = text_field(data, "subject", "学科", default="综合", max_length=30) or "综合"
    if "content_markdown" in data:
        fields["content_markdown"] = text_field(
            data, "content_markdown", "笔记内容", max_length=200000
        )
    if "source_image" in data:
        fields["source_image"] = _source_image_value(
            text_field(data, "source_image", "来源图片", max_length=500), user_id
        )
    if not fields:
        return success(serialize_note(existing), message="没有需要更新的字段")
    fields["updated_at"] = now_iso()
    assignments = ", ".join(f"{column} = ?" for column in fields)
    execute(
        f"UPDATE notes SET {assignments} WHERE id = ? AND user_id = ?",
        (*fields.values(), note_id, user_id),
    )
    return success(
        serialize_note(_get_note_or_404(user_id, note_id)), message="笔记已更新"
    )


@bp.delete("/notes/<int:note_id>")
def delete_note(note_id: int):
    user_id = get_current_user_id()
    _get_note_or_404(user_id, note_id)
    execute("DELETE FROM notes WHERE id = ? AND user_id = ?", (note_id, user_id))
    return success({"deleted_id": note_id}, message="笔记已删除")


@bp.post("/notes/<int:note_id>/audit")
def audit_note(note_id: int):
    user_id = get_current_user_id()
    note = _get_note_or_404(user_id, note_id)
    if not (note["content_markdown"] or "").strip():
        raise APIError("空白笔记无法检查，请先写入内容", code="NOTE_EMPTY", status_code=400)
    data = json_body(required=False)
    demo_requested = bool_field(data, "demo", False)
    features = AIFeatures()
    result, ai_info = features.audit_note(
        note_id=note_id,
        title=note["title"],
        subject=note["subject"],
        markdown=note["content_markdown"],
        demo=demo_requested,
    )
    execute(
        "UPDATE notes SET audit_report = ?, updated_at = ? WHERE id = ? AND user_id = ?",
        (json.dumps(result, ensure_ascii=False), now_iso(), note_id, user_id),
    )
    return success(result, ai=ai_info, message="笔记检查已完成，原始内容未被修改")


@bp.post("/notes/<int:note_id>/graph")
def generate_note_graph(note_id: int):
    user_id = get_current_user_id()
    note = _get_note_or_404(user_id, note_id)
    if not (note["content_markdown"] or "").strip():
        raise APIError("空白笔记无法生成知识图", code="NOTE_EMPTY", status_code=400)
    data = json_body(required=False)
    demo_requested = bool_field(data, "demo", False)
    features = AIFeatures()
    result, ai_info = features.knowledge_graph(
        note_id=note_id,
        title=note["title"],
        subject=note["subject"],
        markdown=note["content_markdown"],
        demo=demo_requested,
    )
    execute(
        "UPDATE notes SET knowledge_graph = ?, updated_at = ? WHERE id = ? AND user_id = ?",
        (json.dumps(result, ensure_ascii=False), now_iso(), note_id, user_id),
    )
    return success(result, ai=ai_info, message="知识关系图已生成")


@bp.get("/notes/<int:note_id>/graph")
def get_note_graph(note_id: int):
    row = _get_note_or_404(get_current_user_id(), note_id)
    if not row["knowledge_graph"]:
        raise NotFound("这篇笔记还没有生成知识关系图", code="GRAPH_NOT_FOUND")
    try:
        data = json.loads(row["knowledge_graph"])
    except ValueError as exc:
        raise APIError("已保存的知识图数据损坏", code="GRAPH_CORRUPTED", status_code=500) from exc
    return success(data)
