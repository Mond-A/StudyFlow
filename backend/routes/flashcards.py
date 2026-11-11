"""Spaced-repetition flashcard CRUD and review flow."""

from __future__ import annotations

from datetime import date, timedelta

from flask import Blueprint, request

from ..db import execute, get_current_user_id, query_all, query_one
from ..services.achievements import evaluate_achievements
from ..utils.exceptions import APIError, NotFound
from ..utils.responses import success
from ..utils.serializers import serialize_flashcard
from ..utils.timeutils import now_iso, today_iso
from ..utils.validators import bool_field, int_field, json_body, query_int, text_field

bp = Blueprint("flashcards", __name__)

INTERVALS = [1, 1, 2, 4, 7, 14]


def _get_card_or_404(user_id: int, card_id: int):
    row = query_one(
        "SELECT * FROM flashcards WHERE id = ? AND user_id = ?", (card_id, user_id)
    )
    if not row:
        raise NotFound("闪卡不存在或已被删除")
    return row


def _validate_note_id(user_id: int, note_id):
    if note_id in (None, ""):
        return None
    try:
        note_id = int(note_id)
    except (TypeError, ValueError) as exc:
        raise APIError("笔记 ID 无效", code="VALIDATION_ERROR", status_code=400) from exc
    row = query_one(
        "SELECT id FROM notes WHERE id = ? AND user_id = ?", (note_id, user_id)
    )
    if not row:
        raise APIError("关联的笔记不存在", code="NOTE_NOT_FOUND", status_code=404)
    return note_id


@bp.get("/flashcards")
def list_flashcards():
    user_id = get_current_user_id()
    due_only = bool_field(
        {"value": request.args.get("due_only")}, "value", False
    )
    subject = (request.args.get("subject") or "").strip()
    limit = query_int("limit", 200, minimum=1, maximum=500)
    conditions = ["user_id = ?"]
    params: list = [user_id]
    if due_only:
        conditions.append("(next_review_date IS NULL OR next_review_date <= ?)")
        params.append(today_iso())
    if subject and subject != "all":
        conditions.append("subject = ?")
        params.append(subject)
    rows = query_all(
        f"""
        SELECT * FROM flashcards WHERE {' AND '.join(conditions)}
        ORDER BY COALESCE(next_review_date, '0000-00-00') ASC, id DESC LIMIT ?
        """,
        (*params, limit),
    )
    cards = [serialize_flashcard(row) for row in rows]
    due_count = sum(1 for card in cards if card["is_due"])
    subject_rows = query_all(
        "SELECT DISTINCT subject FROM flashcards WHERE user_id = ? ORDER BY subject",
        (user_id,),
    )
    return success(
        {
            "flashcards": cards,
            "due_count": due_count,
            "total": len(cards),
            "subjects": [row["subject"] for row in subject_rows],
            "filters": {"due_only": due_only, "subject": subject or "all"},
        }
    )


@bp.post("/flashcards")
def create_flashcard():
    user_id = get_current_user_id()
    data = json_body()
    front = text_field(data, "front", "卡片正面", required=True, max_length=1000)
    back = text_field(data, "back", "卡片背面", required=True, max_length=5000)
    subject = text_field(data, "subject", "学科", default="综合", max_length=30) or "综合"
    note_id = _validate_note_id(user_id, data.get("note_id"))
    next_review_date = data.get("next_review_date") or today_iso()
    if not isinstance(next_review_date, str) or len(next_review_date) != 10:
        next_review_date = today_iso()
    timestamp = now_iso()
    cursor = execute(
        """
        INSERT INTO flashcards
            (user_id, note_id, front, back, subject, mastery_level,
             review_count, next_review_date, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, 0, 0, ?, ?, ?)
        """,
        (
            user_id,
            note_id,
            front,
            back,
            subject,
            next_review_date,
            timestamp,
            timestamp,
        ),
    )
    evaluate_achievements(user_id)
    row = _get_card_or_404(user_id, cursor.lastrowid)
    return success(serialize_flashcard(row), status=201, message="闪卡已创建")


@bp.route("/flashcards/<int:card_id>", methods=["PUT", "PATCH"])
def update_flashcard(card_id: int):
    user_id = get_current_user_id()
    existing = _get_card_or_404(user_id, card_id)
    data = json_body()
    fields = {}
    if "front" in data:
        fields["front"] = text_field(data, "front", "卡片正面", required=True, max_length=1000)
    if "back" in data:
        fields["back"] = text_field(data, "back", "卡片背面", required=True, max_length=5000)
    if "subject" in data:
        fields["subject"] = text_field(data, "subject", "学科", default="综合", max_length=30) or "综合"
    if "note_id" in data:
        fields["note_id"] = _validate_note_id(user_id, data.get("note_id"))
    if "mastery_level" in data:
        fields["mastery_level"] = int_field(
            data, "mastery_level", "掌握程度", default=0, minimum=0, maximum=5
        )
    if "next_review_date" in data:
        value = data.get("next_review_date")
        fields["next_review_date"] = value if isinstance(value, str) and len(value) == 10 else None
    if not fields:
        return success(serialize_flashcard(existing), message="没有需要更新的字段")
    fields["updated_at"] = now_iso()
    assignments = ", ".join(f"{column} = ?" for column in fields)
    execute(
        f"UPDATE flashcards SET {assignments} WHERE id = ? AND user_id = ?",
        (*fields.values(), card_id, user_id),
    )
    return success(
        serialize_flashcard(_get_card_or_404(user_id, card_id)), message="闪卡已更新"
    )


@bp.delete("/flashcards/<int:card_id>")
def delete_flashcard(card_id: int):
    user_id = get_current_user_id()
    _get_card_or_404(user_id, card_id)
    execute(
        "DELETE FROM flashcards WHERE id = ? AND user_id = ?", (card_id, user_id)
    )
    return success({"deleted_id": card_id}, message="闪卡已删除")


@bp.post("/flashcards/<int:card_id>/review")
def review_flashcard(card_id: int):
    user_id = get_current_user_id()
    card = _get_card_or_404(user_id, card_id)
    data = json_body()
    rating = int_field(
        data, "rating", "复习评分", default=3, required=True, minimum=0, maximum=5
    )
    mastery = int(card["mastery_level"])
    if rating >= 4:
        new_mastery = min(5, mastery + 1)
    elif rating == 3:
        new_mastery = mastery
    else:
        new_mastery = max(0, mastery - 1)
    interval = INTERVALS[new_mastery]
    next_review = (date.fromisoformat(today_iso()) + timedelta(days=interval)).isoformat()
    timestamp = now_iso()
    execute(
        """
        UPDATE flashcards
        SET mastery_level = ?, review_count = review_count + 1,
            last_reviewed_at = ?, next_review_date = ?, updated_at = ?
        WHERE id = ? AND user_id = ?
        """,
        (new_mastery, timestamp, next_review, timestamp, card_id, user_id),
    )
    updated = _get_card_or_404(user_id, card_id)
    return success(
        {
            "flashcard": serialize_flashcard(updated),
            "interval_days": interval,
            "message": "已记录本次复习",
        }
    )
