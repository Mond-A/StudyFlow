"""Business-level AI features plus defensive normalization of model output.

The API contract exposed to the frontend is stable even when a model omits a
field or returns a slightly different shape. Critical shape errors trigger the
gateway's limited retry instead of producing broken UI data.
"""

from __future__ import annotations

import re
from datetime import datetime

from flask import current_app

from ..utils.exceptions import AIServiceError
from ..utils.timeutils import now_iso
from . import ai_prompts
from .ai_service import AIService, DEMO_NOTICE, GENERAL_DISCLAIMER
from . import demo_ai

CORRECTION_CATEGORIES = {
    "拼写",
    "语法",
    "时态",
    "句式",
    "词汇",
    "结构",
    "标点",
    "标点/大小写",
}
AUDIT_CATEGORIES = {
    "知识性错误",
    "公式错误",
    "概念混淆",
    "逻辑矛盾",
    "识别错误",
    "其他",
}
GRAPH_TYPES = {"概念", "公式", "定理", "方法", "应用"}
GRAPH_RELATIONS = {"前置知识", "从属关系", "相互关联", "应用关系"}


def _text(value, default: str = "", max_length: int = 20000) -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        value = str(value)
    return value.strip()[:max_length]


def _list_of_text(value, *, max_items: int = 12, max_length: int = 300) -> list[str]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value[:max_items]:
        if isinstance(item, (str, int, float)):
            text = str(item).strip()
            if text:
                result.append(text[:max_length])
    return result


def _int(value, default: int, minimum: int, maximum: int) -> int:
    try:
        return max(minimum, min(maximum, int(float(value))))
    except (TypeError, ValueError):
        return default


def _float(value, default: float, minimum: float, maximum: float) -> float:
    try:
        return max(minimum, min(maximum, float(value)))
    except (TypeError, ValueError):
        return default


def _dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _list(value) -> list:
    return value if isinstance(value, list) else []


def _certainty(value) -> str:
    return value if value in {"certain", "review"} else "review"


def _strip_code(value: str) -> str:
    value = value.strip()
    if value.startswith("```"):
        value = re.sub(r"^```[a-zA-Z]*\s*", "", value)
        value = re.sub(r"\s*```$", "", value)
    return value.strip()


def _level_from_percentage(percentage: float) -> str:
    if percentage >= 90:
        return "优秀"
    if percentage >= 75:
        return "良好"
    if percentage >= 60:
        return "及格"
    return "待提升"


def _clean_warnings(value) -> list[str]:
    return _list_of_text(value, max_items=8, max_length=300)


# ── normalizers ────────────────────────────────────────────────────────


def _normalize_tasks(raw: dict, payload: dict) -> dict:
    if "tasks" not in raw or not isinstance(raw.get("tasks"), list):
        raise ValueError("tasks must be a list")
    default_subject = payload.get("subject_hint") or "综合"
    warning = _clean_warnings(raw.get("warnings"))
    tasks = []
    for item in raw.get("tasks", [])[:15]:
        if not isinstance(item, dict):
            continue
        title = _text(item.get("title"), max_length=120)
        if not title:
            continue
        description = _text(item.get("description"), max_length=1500)
        question_count = item.get("question_count")
        try:
            question_count = int(question_count) if question_count is not None else None
        except (TypeError, ValueError):
            question_count = None
        confidence = _float(item.get("confidence"), 0.5, 0, 1)
        due = _text(item.get("due_date"), max_length=10) or payload.get("due_date")
        if due and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", due):
            due = payload.get("due_date") or None
        tasks.append(
            {
                "title": title,
                "subject": _text(item.get("subject"), default_subject, 30) or default_subject,
                "description": description,
                "question_count": question_count,
                "difficulty": _int(item.get("difficulty"), 3, 1, 5),
                "estimated_minutes": _int(item.get("estimated_minutes"), 40, 5, 240),
                "difficulty_reason": _text(
                    item.get("difficulty_reason"), max_length=500
                ),
                "confidence": round(confidence, 2),
                "due_date": due,
            }
        )
    if not tasks and raw.get("tasks") and not warning:
        warning.append("模型返回的作业任务字段不完整，未生成可添加的条目。")
    return {
        "image_summary": _text(raw.get("image_summary"), max_length=1000),
        "tasks": tasks,
        "warnings": warning,
    }


def _normalize_note_recognition(raw: dict, payload: dict) -> dict:
    markdown = _strip_code(_text(raw.get("markdown"), max_length=60000))
    if not markdown:
        raise ValueError("markdown is required")
    subject = _text(raw.get("subject"), payload.get("subject_hint") or "综合", 30)
    title = _text(raw.get("title"), payload.get("title_hint") or "识别笔记", 120)
    return {
        "title": title or "识别笔记",
        "subject": subject or "综合",
        "markdown": markdown,
        "confidence": round(_float(raw.get("confidence"), 0.5, 0, 1), 2),
        "warnings": _clean_warnings(raw.get("warnings")),
        "source": "vision-recognition",
    }


def _normalize_essay(raw: dict, payload: dict) -> dict:
    overall = _dict(raw.get("overall"))
    provided_text = _text(payload.get("text"), max_length=30000)
    recognized = _text(raw.get("recognized_text"), max_length=30000) or provided_text
    corrections = []
    for item in _list(raw.get("corrections"))[:25]:
        if not isinstance(item, dict):
            continue
        original = _text(item.get("original"), max_length=500)
        suggestion = _text(item.get("suggestion"), max_length=1000)
        if not original and not suggestion:
            continue
        category = _text(item.get("category"), "其他", 20)
        if category not in CORRECTION_CATEGORIES:
            category = "其他"
        corrections.append(
            {
                "category": category,
                "original": original,
                "suggestion": suggestion,
                "explanation": _text(item.get("explanation"), max_length=1000),
                "certainty": _certainty(item.get("certainty")),
            }
        )
    structure = _dict(raw.get("structure"))
    word_usage = _dict(raw.get("word_usage"))
    corrected = _text(raw.get("corrected_text"), max_length=40000) or provided_text
    if not recognized and not corrected:
        raise ValueError("essay review returned no text")
    score = _int(overall.get("score"), 0, 0, 100)
    word_count = _int(
        raw.get("word_count"), len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", recognized or corrected)), 0, 10000
    )
    return {
        "recognized_text": recognized,
        "overall": {
            "score": score,
            "level": _text(overall.get("level"), _level_from_percentage(score), 20),
            "summary": _text(overall.get("summary"), max_length=2000),
        },
        "corrected_text": corrected,
        "corrections": corrections,
        "structure": {
            "strengths": _list_of_text(structure.get("strengths")),
            "improvements": _list_of_text(structure.get("improvements")),
        },
        "word_usage": {
            "strengths": _list_of_text(word_usage.get("strengths")),
            "improvements": _list_of_text(word_usage.get("improvements")),
        },
        "next_steps": _list_of_text(raw.get("next_steps"), max_items=8),
        "word_count": word_count,
        "warnings": _clean_warnings(raw.get("warnings")),
    }


def _normalize_polish(raw: dict, payload: dict) -> dict:
    original = _text(payload.get("text"), max_length=20000)
    versions = {}
    for key in ("simple", "natural", "advanced"):
        version = _dict(raw.get(key))
        versions[key] = {
            "text": _text(version.get("text"), max_length=20000)
            or (original if key == "simple" else ""),
            "explanation": _text(version.get("explanation"), max_length=1000),
        }
    if not any(version["text"] for version in versions.values()):
        raise ValueError("polish versions are empty")
    return {
        "meaning_notes": _text(raw.get("meaning_notes"), max_length=1500),
        "simple": versions["simple"],
        "natural": versions["natural"],
        "advanced": versions["advanced"],
        "warnings": _clean_warnings(raw.get("warnings")),
    }


def _normalize_sentence(raw: dict, payload: dict) -> dict:
    original = _text(payload.get("sentence"), max_length=3000)
    components = _dict(raw.get("components"))
    clauses = []
    for item in _list(raw.get("clauses"))[:12]:
        if not isinstance(item, dict):
            continue
        clauses.append(
            {
                "type": _text(item.get("type"), "其他", 30),
                "text": _text(item.get("text"), max_length=1000),
                "function": _text(item.get("function"), max_length=800),
            }
        )
    return {
        "original": _text(raw.get("original"), original, 3000) or original,
        "main_clause": _text(raw.get("main_clause"), max_length=3000),
        "clauses": clauses,
        "components": {
            "subject": _text(components.get("subject"), max_length=500),
            "predicate": _text(components.get("predicate"), max_length=500),
            "object": _text(components.get("object"), max_length=500) or None,
            "attributes": _list_of_text(components.get("attributes"), max_items=10),
            "adverbials": _list_of_text(components.get("adverbials"), max_items=10),
        },
        "structure_summary": _text(raw.get("structure_summary"), max_length=3000),
        "key_points": _list_of_text(raw.get("key_points"), max_items=10),
        "translation": _text(raw.get("translation"), max_length=3000),
        "caution": _text(raw.get("caution"), max_length=1000),
        "warnings": _clean_warnings(raw.get("warnings")),
    }


def _normalize_grammar(raw: dict, payload: dict) -> dict:
    issues = []
    for item in _list(raw.get("issues"))[:20]:
        if not isinstance(item, dict):
            continue
        issues.append(
            {
                "type": _text(item.get("type"), "其他", 30),
                "original": _text(item.get("original"), max_length=500),
                "suggestion": _text(item.get("suggestion"), max_length=500),
                "explanation": _text(item.get("explanation"), max_length=1000),
                "certainty": _certainty(item.get("certainty")),
            }
        )
    sentence = _text(payload.get("sentence"), max_length=3000)
    return {
        "original": _text(raw.get("original"), sentence, 3000),
        "corrected_text": _text(raw.get("corrected_text"), sentence, 3000),
        "is_correct": bool(raw.get("is_correct", not issues)),
        "issues": issues,
        "overall": _text(raw.get("overall"), max_length=1500),
        "warnings": _clean_warnings(raw.get("warnings")),
    }


def _normalize_questions(raw: dict, payload: dict) -> dict:
    questions = []
    raw_questions = raw.get("questions")
    if not isinstance(raw_questions, list):
        raise ValueError("questions must be a list")
    for index, item in enumerate(raw_questions[:10]):
        if not isinstance(item, dict):
            continue
        question = _text(item.get("question"), max_length=4000)
        answer = _text(item.get("answer"), max_length=4000)
        if not question or not answer:
            continue
        questions.append(
            {
                "number": _int(item.get("number"), index + 1, 1, 99),
                "type": _text(item.get("type"), "简答题", 20),
                "question": question,
                "options": _list_of_text(item.get("options"), max_items=8, max_length=500),
                "answer": answer,
                "explanation": _text(item.get("explanation"), max_length=4000),
            }
        )
    if not questions:
        raise ValueError("no complete questions returned")
    return {
        "subject": _text(raw.get("subject"), payload.get("subject") or "综合", 30),
        "topic": _text(raw.get("topic"), payload.get("topic") or "", 120),
        "difficulty": _text(raw.get("difficulty"), payload.get("difficulty") or "medium", 20),
        "questions": questions,
        "warnings": _clean_warnings(raw.get("warnings")),
    }


def _normalize_grading(raw: dict, payload: dict) -> dict:
    try:
        max_score = max(1.0, min(1000.0, float(payload.get("max_score") or 100)))
    except (TypeError, ValueError):
        max_score = 100.0
    score = round(_float(raw.get("score"), 0, 0, max_score), 1)
    percentage = score / max_score * 100 if max_score else 0
    matched = []
    for item in _list(raw.get("matched_points"))[:15]:
        if isinstance(item, dict):
            point = _text(item.get("point"), max_length=1000)
            if point:
                matched.append(
                    {
                        "point": point,
                        "evidence": _text(item.get("evidence"), max_length=1000),
                    }
                )
    missing = []
    for item in _list(raw.get("missing_points"))[:15]:
        if isinstance(item, dict):
            point = _text(item.get("point"), max_length=1000)
            if point:
                missing.append(
                    {
                        "point": point,
                        "suggestion": _text(item.get("suggestion"), max_length=1000),
                    }
                )
    deductions = []
    for item in _list(raw.get("deductions"))[:15]:
        if isinstance(item, dict):
            deductions.append(
                {
                    "reason": _text(item.get("reason"), max_length=1000),
                    "points": _float(item.get("points"), 0, 0, max_score),
                }
            )
    return {
        "score": score,
        "max_score": max_score,
        "level": _text(raw.get("level"), _level_from_percentage(percentage), 20),
        "matched_points": matched,
        "missing_points": missing,
        "deductions": deductions,
        "comment": _text(raw.get("comment"), max_length=3000),
        "improvement": _list_of_text(raw.get("improvement"), max_items=10),
        "confidence": _text(raw.get("confidence"), "low", 10),
        "warnings": _clean_warnings(raw.get("warnings")),
    }


def _normalize_grade_analysis(raw: dict, payload: dict) -> dict:
    trend = _dict(raw.get("trend"))
    strengths = []
    for item in _list(raw.get("strengths"))[:4]:
        if isinstance(item, dict):
            strengths.append(
                {
                    "subject": _text(item.get("subject"), max_length=30),
                    "evidence": _text(item.get("evidence"), max_length=1000),
                    "observation": _text(item.get("observation"), max_length=1000),
                }
            )
    weaknesses = []
    for item in _list(raw.get("weaknesses"))[:4]:
        if isinstance(item, dict):
            weaknesses.append(
                {
                    "subject": _text(item.get("subject"), max_length=30),
                    "evidence": _text(item.get("evidence"), max_length=1000),
                    "observation": _text(item.get("observation"), max_length=1000),
                }
            )
    suggestions = []
    for item in _list(raw.get("suggestions"))[:6]:
        if isinstance(item, dict):
            title = _text(item.get("title"), max_length=200)
            detail = _text(item.get("detail"), max_length=1500)
            if title or detail:
                priority = _text(item.get("priority"), "中", 10)
                suggestions.append(
                    {
                        "title": title,
                        "detail": detail,
                        "priority": priority if priority in {"高", "中", "低"} else "中",
                    }
                )
    return {
        "summary": _text(raw.get("summary"), max_length=2500),
        "trend": {
            "direction": _text(trend.get("direction"), "暂时无法判断", 20),
            "explanation": _text(trend.get("explanation"), max_length=1500),
            "limitations": _text(trend.get("limitations"), max_length=2000)
            or "样本有限，趋势仅描述已有记录。",
        },
        "strengths": strengths,
        "weaknesses": weaknesses,
        "suggestions": suggestions,
        "disclaimer": "本分析仅基于有限成绩记录，仅供参考，不构成分数预测或正式评价。",
        "warnings": _clean_warnings(raw.get("warnings")),
    }


def _normalize_audit(raw: dict, payload: dict) -> dict:
    corrections = []
    for item in _list(raw.get("corrections"))[:30]:
        if not isinstance(item, dict):
            continue
        original = _text(item.get("original"), max_length=1000)
        suggested = _text(item.get("suggested"), max_length=2000)
        if not original and not suggested:
            continue
        category = _text(item.get("category"), "其他", 20)
        if category not in AUDIT_CATEGORIES:
            category = "其他"
        corrections.append(
            {
                "location": _text(item.get("location"), max_length=200),
                "original": original,
                "suggested": suggested,
                "reason": _text(item.get("reason"), max_length=1500),
                "certainty": _certainty(item.get("certainty")),
                "confidence": round(
                    _float(
                        item.get("confidence"),
                        0.75 if _certainty(item.get("certainty")) == "certain" else 0.4,
                        0,
                        1,
                    ),
                    2,
                ),
                "category": category,
            }
        )
    return {
        "summary": _text(raw.get("summary"), max_length=2500),
        "corrections": corrections,
        "no_issues": not corrections,
        "coverage_note": _text(raw.get("coverage_note"), max_length=2500),
        "warnings": _clean_warnings(raw.get("warnings")),
        "checked_at": now_iso(),
        "source_note_id": payload.get("note_id"),
    }


def _normalize_graph(raw: dict, payload: dict) -> dict:
    raw_nodes = raw.get("nodes")
    if raw_nodes is None or not isinstance(raw_nodes, list):
        raise ValueError("nodes must be a list")
    nodes = []
    seen_ids = set()
    for index, item in enumerate(raw_nodes[:30]):
        if not isinstance(item, dict):
            continue
        node_id = _text(item.get("id"), f"node-{index + 1}", 80)
        node_id = re.sub(r"[^a-zA-Z0-9_\-.]", "-", node_id) or f"node-{index + 1}"
        if node_id in seen_ids:
            node_id = f"{node_id}-{index + 1}"
        label = _text(item.get("label"), max_length=80)
        if not label:
            continue
        seen_ids.add(node_id)
        node_type = _text(item.get("type"), "概念", 20)
        if node_type not in GRAPH_TYPES:
            node_type = "概念"
        nodes.append(
            {
                "id": node_id,
                "label": label,
                "type": node_type,
                "description": _text(item.get("description"), max_length=500),
            }
        )
    edges = []
    edge_keys = set()
    for item in _list(raw.get("edges"))[:80]:
        if not isinstance(item, dict):
            continue
        source = _text(item.get("source"), max_length=80)
        target = _text(item.get("target"), max_length=80)
        if (
            source not in seen_ids
            or target not in seen_ids
            or source == target
            or (source, target) in edge_keys
        ):
            continue
        relation = _text(item.get("label"), "相互关联", 20)
        if relation not in GRAPH_RELATIONS:
            relation = "相互关联"
        edge_keys.add((source, target))
        edges.append({"source": source, "target": target, "label": relation})
    if not nodes:
        raise ValueError("no usable graph nodes returned")
    return {
        "nodes": nodes,
        "edges": edges,
        "summary": _text(raw.get("summary"), max_length=1500),
        "warnings": _clean_warnings(raw.get("warnings")),
        "generated_at": now_iso(),
        "source_note_id": payload.get("note_id"),
    }


def _normalize_flashcards(raw: dict, payload: dict) -> dict:
    try:
        count = max(1, min(int(payload.get("count") or 5), 20))
    except (TypeError, ValueError):
        count = 5
    cards = []
    seen = set()
    for item in _list(raw.get("cards"))[:count]:
        if not isinstance(item, dict):
            continue
        front = _text(item.get("front"), max_length=500)
        back = _text(item.get("back"), max_length=2000)
        if not front or not back or front in seen:
            continue
        seen.add(front)
        cards.append(
            {
                "front": front,
                "back": back,
                "knowledge_point": _text(item.get("knowledge_point"), max_length=120),
            }
        )
    return {
        "cards": cards,
        "summary": _text(raw.get("summary"), max_length=1000),
        "warnings": _clean_warnings(raw.get("warnings")),
    }


def _normalize_error_classification(raw: dict, payload: dict) -> dict:
    subject = _text(raw.get("subject"), payload.get("subject_hint") or "综合", 30)
    confidence = _text(raw.get("confidence"), "low", 10)
    if confidence not in {"high", "medium", "low"}:
        confidence = "low"
    mastery = _text(raw.get("mastery_hint"), "new", 20)
    if mastery not in {"new", "reviewing"}:
        mastery = "new"
    return {
        "subject": subject or "综合",
        "knowledge_points": _list_of_text(
            raw.get("knowledge_points"), max_items=8, max_length=80
        ),
        "analysis": _text(raw.get("analysis"), max_length=2000),
        "suggested_review": _text(raw.get("suggested_review"), max_length=1500),
        "mastery_hint": mastery,
        "confidence": confidence,
        "warnings": _clean_warnings(raw.get("warnings")),
    }


# ── feature facade ─────────────────────────────────────────────────────


class AIFeatures:
    def __init__(self, service: AIService | None = None):
        self.service = service or AIService.from_app()

    @staticmethod
    def _apply_demo_warnings(result: dict) -> dict:
        warnings = list(result.get("warnings") or [])
        # The demo builders already include a prominent mode warning. Avoid
        # stacking two nearly identical paragraphs in the UI.
        has_demo_warning = any(
            isinstance(item, str) and item.startswith("当前为演示模式") for item in warnings
        )
        if DEMO_NOTICE not in warnings and not has_demo_warning:
            warnings.insert(0, DEMO_NOTICE)
        result["warnings"] = warnings
        return result

    def _run(
        self,
        *,
        capability: str,
        system_prompt: str,
        user_prompt: str,
        demo_builder,
        demo_payload: dict,
        validator,
        images: list[str] | None = None,
        demo_requested: bool = False,
        temperature: float = 0.2,
        max_tokens: int = 3500,
    ) -> tuple[dict, dict]:
        mode_info = self.service.resolve_mode(
            capability, demo_requested=demo_requested
        )
        if mode_info["mode"] == "demo":
            try:
                result = validator(demo_builder(demo_payload), demo_payload)
            except (ValueError, TypeError, KeyError) as exc:
                raise AIServiceError(
                    "演示模式数据生成失败",
                    code="DEMO_DATA_ERROR",
                    status_code=500,
                    details={"reason": str(exc)},
                ) from exc
            result = self._apply_demo_warnings(result)
            mode_info["demo_requested"] = True
            return result, mode_info

        validated, usage, live_info = self.service.complete_json(
            capability=capability,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            images=images,
            validator=lambda raw: validator(raw, demo_payload),
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if usage:
            live_info["usage"] = usage
        return validated, live_info

    # Individual tool methods are intentionally thin wrappers.
    def recognize_tasks(
        self, *, image_url: str, image_data_url: str, subject_hint=None, due_date=None, demo=False
    ):
        payload = {"subject_hint": subject_hint, "due_date": due_date, "image_url": image_url}
        return self._run(
            capability="vision",
            system_prompt=ai_prompts.BASE_SYSTEM,
            user_prompt=ai_prompts.task_recognition_prompt(subject_hint, due_date),
            demo_builder=demo_ai.recognize_tasks_demo,
            demo_payload=payload,
            validator=_normalize_tasks,
            images=[image_data_url],
            demo_requested=demo,
        )

    def recognize_note(
        self, *, image_url: str, image_data_url: str, title_hint=None, demo=False
    ):
        payload = {"title_hint": title_hint, "image_url": image_url}
        return self._run(
            capability="vision",
            system_prompt=ai_prompts.BASE_SYSTEM,
            user_prompt=ai_prompts.note_recognition_prompt(title_hint),
            demo_builder=demo_ai.recognize_note_demo,
            demo_payload=payload,
            validator=_normalize_note_recognition,
            images=[image_data_url],
            demo_requested=demo,
            temperature=0.1,
            max_tokens=5000,
        )

    def review_essay(self, *, text=None, image_url=None, image_data_url=None, demo=False):
        capability = "vision" if image_data_url else "text"
        payload = {"text": text, "image_url": image_url}
        images = [image_data_url] if image_data_url else None
        return self._run(
            capability=capability,
            system_prompt=ai_prompts.BASE_SYSTEM,
            user_prompt=ai_prompts.essay_review_prompt(text, bool(image_data_url)),
            demo_builder=demo_ai.review_essay_demo,
            demo_payload=payload,
            validator=_normalize_essay,
            images=images,
            demo_requested=demo,
        )

    def polish(self, *, text: str, demo=False):
        payload = {"text": text}
        return self._run(
            capability="text",
            system_prompt=ai_prompts.BASE_SYSTEM,
            user_prompt=ai_prompts.polish_prompt(text),
            demo_builder=demo_ai.polish_demo,
            demo_payload=payload,
            validator=_normalize_polish,
            demo_requested=demo,
        )

    def analyze_sentence(self, *, sentence: str, demo=False):
        payload = {"sentence": sentence}
        return self._run(
            capability="text",
            system_prompt=ai_prompts.BASE_SYSTEM,
            user_prompt=ai_prompts.sentence_analysis_prompt(sentence),
            demo_builder=demo_ai.analyze_sentence_demo,
            demo_payload=payload,
            validator=_normalize_sentence,
            demo_requested=demo,
        )

    def check_grammar(self, *, sentence: str, demo=False):
        payload = {"sentence": sentence}
        return self._run(
            capability="text",
            system_prompt=ai_prompts.BASE_SYSTEM,
            user_prompt=ai_prompts.grammar_check_prompt(sentence),
            demo_builder=demo_ai.check_grammar_demo,
            demo_payload=payload,
            validator=_normalize_grammar,
            demo_requested=demo,
        )

    def generate_questions(
        self, *, subject: str, topic: str, difficulty: str, count: int, demo=False
    ):
        payload = {
            "subject": subject,
            "topic": topic,
            "difficulty": difficulty,
            "count": count,
        }
        return self._run(
            capability="text",
            system_prompt=ai_prompts.BASE_SYSTEM,
            user_prompt=ai_prompts.question_generation_prompt(
                subject, topic, difficulty, count
            ),
            demo_builder=demo_ai.generate_questions_demo,
            demo_payload=payload,
            validator=_normalize_questions,
            demo_requested=demo,
            temperature=0.35,
        )

    def grade_answer(
        self,
        *,
        question: str,
        reference_answer: str,
        student_answer: str,
        max_score: float,
        demo=False,
    ):
        payload = {
            "question": question,
            "reference_answer": reference_answer,
            "student_answer": student_answer,
            "max_score": max_score,
        }
        return self._run(
            capability="text",
            system_prompt=ai_prompts.BASE_SYSTEM,
            user_prompt=ai_prompts.grading_prompt(
                question, reference_answer, student_answer, max_score
            ),
            demo_builder=demo_ai.grade_answer_demo,
            demo_payload=payload,
            validator=_normalize_grading,
            demo_requested=demo,
        )

    def analyze_grades(self, *, analytics: dict, demo=False):
        payload = {"analytics": analytics}
        return self._run(
            capability="text",
            system_prompt=ai_prompts.BASE_SYSTEM,
            user_prompt=ai_prompts.grade_analysis_prompt(analytics),
            demo_builder=demo_ai.analyze_grades_demo,
            demo_payload=payload,
            validator=_normalize_grade_analysis,
            demo_requested=demo,
        )

    def audit_note(
        self, *, note_id, title: str, subject: str, markdown: str, demo=False
    ):
        payload = {
            "note_id": note_id,
            "title": title,
            "subject": subject,
            "markdown": markdown,
        }
        return self._run(
            capability="text",
            system_prompt=ai_prompts.BASE_SYSTEM,
            user_prompt=ai_prompts.note_audit_prompt(title, subject, markdown),
            demo_builder=demo_ai.audit_note_demo,
            demo_payload=payload,
            validator=_normalize_audit,
            demo_requested=demo,
        )

    def knowledge_graph(
        self, *, note_id, title: str, subject: str, markdown: str, demo=False
    ):
        payload = {
            "note_id": note_id,
            "title": title,
            "subject": subject,
            "markdown": markdown,
        }
        return self._run(
            capability="text",
            system_prompt=ai_prompts.BASE_SYSTEM,
            user_prompt=ai_prompts.knowledge_graph_prompt(title, subject, markdown),
            demo_builder=demo_ai.knowledge_graph_demo,
            demo_payload=payload,
            validator=_normalize_graph,
            demo_requested=demo,
            temperature=0.15,
        )

    def generate_flashcards(
        self,
        *,
        note_id,
        title: str,
        subject: str,
        markdown: str,
        count: int,
        demo=False,
    ):
        payload = {
            "note_id": note_id,
            "title": title,
            "subject": subject,
            "markdown": markdown,
            "count": count,
        }
        return self._run(
            capability="text",
            system_prompt=ai_prompts.BASE_SYSTEM,
            user_prompt=ai_prompts.flashcard_prompt(title, subject, markdown, count),
            demo_builder=demo_ai.generate_flashcards_demo,
            demo_payload=payload,
            validator=_normalize_flashcards,
            demo_requested=demo,
        )

    def classify_error(
        self,
        *,
        question: str,
        student_answer: str,
        subject_hint=None,
        demo=False,
    ):
        payload = {
            "question": question,
            "student_answer": student_answer,
            "subject_hint": subject_hint,
            "title": question[:80],
        }
        return self._run(
            capability="text",
            system_prompt=ai_prompts.BASE_SYSTEM,
            user_prompt=ai_prompts.error_classification_prompt(
                question, student_answer, subject_hint
            ),
            demo_builder=demo_ai.classify_error_demo,
            demo_payload=payload,
            validator=_normalize_error_classification,
            demo_requested=demo,
        )
