"""AI toolbox, vision recognition and structured AI tool endpoints."""

from __future__ import annotations

from flask import Blueprint, request

from ..db import get_current_user_id, query_one
from ..services.achievements import evaluate_achievements
from ..services.ai_features import AIFeatures
from ..services.ai_service import AIService
from ..services.analytics import grade_analytics
from ..utils.exceptions import APIError, NotFound
from ..utils.responses import success
from ..utils.timeutils import today_iso
from ..utils.uploads import load_upload_data_url
from ..utils.validators import (
    bool_field,
    choice_field,
    date_field,
    float_field,
    int_field,
    json_body,
    text_field,
)

bp = Blueprint("ai", __name__)


def _demo_flag(data: dict) -> bool:
    return bool_field(data, "demo", False)


def _image_data(data: dict, user_id: int) -> tuple[str, str] | tuple[None, None]:
    image_url = text_field(data, "image_url", "图片地址", max_length=500)
    if not image_url:
        return None, None
    return image_url, load_upload_data_url(image_url, user_id)


@bp.get("/ai/status")
def ai_status():
    service = AIService.from_app()
    return success(service.status())


@bp.post("/ai/tasks/recognize")
def recognize_tasks():
    data = json_body()
    image_url, image_data = _image_data(data, get_current_user_id())
    if not image_url:
        raise APIError(
            "请先上传作业图片", code="IMAGE_REQUIRED", status_code=400
        )
    subject_hint = text_field(data, "subject_hint", "学科提示", max_length=30) or None
    due_date = date_field(data, "due_date", "截止日期")
    features = AIFeatures()
    result, ai_info = features.recognize_tasks(
        image_url=image_url,
        image_data_url=image_data,
        subject_hint=subject_hint,
        due_date=due_date,
        demo=_demo_flag(data),
    )
    return success(result, ai=ai_info)


@bp.post("/ai/notes/recognize")
def recognize_note():
    data = json_body()
    image_url, image_data = _image_data(data, get_current_user_id())
    if not image_url:
        raise APIError(
            "请先上传笔记图片", code="IMAGE_REQUIRED", status_code=400
        )
    title_hint = text_field(data, "title_hint", "标题提示", max_length=120) or None
    features = AIFeatures()
    result, ai_info = features.recognize_note(
        image_url=image_url,
        image_data_url=image_data,
        title_hint=title_hint,
        demo=_demo_flag(data),
    )
    return success(result, ai=ai_info)


@bp.post("/ai/essay/review")
def review_essay():
    data = json_body()
    text = text_field(data, "text", "作文内容", max_length=30000)
    image_url = text_field(data, "image_url", "图片地址", max_length=500)
    image_data = (
        load_upload_data_url(image_url, get_current_user_id()) if image_url else None
    )
    if not text and not image_data:
        raise APIError(
            "请输入作文文本或上传作文图片",
            code="ESSAY_REQUIRED",
            status_code=400,
        )
    features = AIFeatures()
    result, ai_info = features.review_essay(
        text=text or None,
        image_url=image_url or None,
        image_data_url=image_data,
        demo=_demo_flag(data),
    )
    return success(result, ai=ai_info)


@bp.post("/ai/express/polish")
def polish_expression():
    data = json_body()
    text = text_field(
        data, "text", "英文表达", required=True, max_length=10000
    )
    features = AIFeatures()
    result, ai_info = features.polish(text=text, demo=_demo_flag(data))
    return success(result, ai=ai_info)


@bp.post("/ai/sentence/analyze")
def analyze_sentence():
    data = json_body()
    sentence = text_field(
        data, "sentence", "英文句子", required=True, max_length=3000
    )
    features = AIFeatures()
    result, ai_info = features.analyze_sentence(
        sentence=sentence, demo=_demo_flag(data)
    )
    return success(result, ai=ai_info)


@bp.post("/ai/grammar/check")
def check_grammar():
    data = json_body()
    sentence = text_field(
        data, "sentence", "英语句子", required=True, max_length=3000
    )
    features = AIFeatures()
    result, ai_info = features.check_grammar(
        sentence=sentence, demo=_demo_flag(data)
    )
    return success(result, ai=ai_info)


@bp.post("/ai/questions/generate")
def generate_questions():
    data = json_body()
    subject = text_field(data, "subject", "学科", required=True, max_length=30)
    topic = text_field(data, "topic", "知识点", required=True, max_length=120)
    difficulty = (
        choice_field(
            data,
            "difficulty",
            "难度",
            {"easy", "medium", "hard"},
            default="medium",
        )
        or "medium"
    )
    count = int_field(data, "count", "题目数量", default=3, minimum=1, maximum=5)
    features = AIFeatures()
    result, ai_info = features.generate_questions(
        subject=subject,
        topic=topic,
        difficulty=difficulty,
        count=count,
        demo=_demo_flag(data),
    )
    return success(result, ai=ai_info)


@bp.post("/ai/grading/assist")
def grading_assist():
    data = json_body()
    question = text_field(data, "question", "题目", required=True, max_length=10000)
    reference = text_field(
        data, "reference_answer", "参考答案", required=True, max_length=10000
    )
    student = text_field(data, "student_answer", "学生答案", max_length=10000)
    max_score = float_field(
        data, "max_score", "满分", default=100, minimum=1, maximum=1000
    )
    features = AIFeatures()
    result, ai_info = features.grade_answer(
        question=question,
        reference_answer=reference,
        student_answer=student,
        max_score=max_score or 100,
        demo=_demo_flag(data),
    )
    return success(result, ai=ai_info)


@bp.post("/ai/grades/analyze")
def analyze_grades():
    user_id = get_current_user_id()
    data = json_body(required=False)
    subject = text_field(data, "subject", "学科", max_length=30) or None
    range_value = text_field(data, "range", "时间范围", default="90", max_length=10) or "90"
    analytics = grade_analytics(
        user_id, subject=subject if subject != "all" else None, range_value=range_value
    )
    compact = {
        "range": analytics["range"],
        "subject_filter": analytics["subject_filter"],
        "kpis": analytics["kpis"],
        "subject_comparison": analytics["subject_comparison"],
        "overall_series": analytics["overall_series"][-40:],
        "chart_records": analytics["chart_records"][-120:],
        "data_range": analytics["data_range"],
    }
    features = AIFeatures()
    result, ai_info = features.analyze_grades(
        analytics=compact, demo=_demo_flag(data)
    )
    return success(result, ai=ai_info)


@bp.post("/ai/errors/classify")
def classify_error():
    data = json_body()
    question = text_field(data, "question", "题目", required=True, max_length=10000)
    student_answer = text_field(data, "student_answer", "学生答案", max_length=10000)
    subject_hint = text_field(data, "subject_hint", "学科提示", max_length=30) or None
    features = AIFeatures()
    result, ai_info = features.classify_error(
        question=question,
        student_answer=student_answer,
        subject_hint=subject_hint,
        demo=_demo_flag(data),
    )
    return success(result, ai=ai_info)


@bp.post("/ai/flashcards/generate")
def generate_flashcards():
    user_id = get_current_user_id()
    data = json_body()
    note_id = data.get("note_id")
    count = int_field(data, "count", "卡片数量", default=5, minimum=1, maximum=20)
    if note_id not in (None, ""):
        try:
            note_id = int(note_id)
        except (TypeError, ValueError) as exc:
            raise APIError("笔记 ID 无效", code="VALIDATION_ERROR", status_code=400) from exc
        note = query_one(
            "SELECT * FROM notes WHERE id = ? AND user_id = ?", (note_id, user_id)
        )
        if not note:
            raise NotFound("笔记不存在")
        title = note["title"]
        subject = note["subject"]
        markdown = note["content_markdown"]
    else:
        title = text_field(data, "title", "标题", default="未命名笔记", max_length=180)
        subject = text_field(data, "subject", "学科", default="综合", max_length=30) or "综合"
        markdown = text_field(
            data, "markdown", "笔记内容", required=True, max_length=200000
        )
    if not (markdown or "").strip():
        raise APIError("笔记内容为空，无法生成闪卡", code="NOTE_EMPTY", status_code=400)
    features = AIFeatures()
    result, ai_info = features.generate_flashcards(
        note_id=note_id if note_id not in (None, "") else None,
        title=title,
        subject=subject,
        markdown=markdown,
        count=count,
        demo=_demo_flag(data),
    )
    return success(result, ai=ai_info)
