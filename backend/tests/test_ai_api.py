"""AI endpoint tests, all using the explicit local demo mode (no network)."""

from __future__ import annotations

import io

from backend.services.ai_service import AIService
from .conftest import assert_ok, authenticate_client


def test_upload_validation_and_serving(client, upload_image):
    uploaded = upload_image()
    assert uploaded["url"].startswith("/uploads/")
    assert uploaded["width"] == 320
    served = client.get(uploaded["url"])
    assert served.status_code == 200
    assert served.mimetype == "image/png"

    invalid = client.post(
        "/api/uploads",
        data={"image": (io.BytesIO(b"not actually an image"), "fake.png")},
        content_type="multipart/form-data",
    )
    assert invalid.status_code == 415
    assert invalid.get_json()["ok"] is False
    assert invalid.get_json()["error"]["code"] in {"INVALID_IMAGE", "UNSUPPORTED_FILE_TYPE"}

    missing = client.post("/api/uploads", data={}, content_type="multipart/form-data")
    assert missing.status_code == 400


def test_vision_task_and_note_recognition_demo(client, upload_image):
    uploaded = upload_image()
    response = client.post(
        "/api/ai/tasks/recognize",
        json={"image_url": uploaded["url"], "subject_hint": "数学"},
    )
    payload = assert_ok(response)
    assert payload["ai"]["mode"] == "demo"
    assert "演示模式" in payload["ai"]["notice"]
    assert payload["data"]["tasks"]
    assert payload["data"]["tasks"][0]["subject"] == "数学"

    response = client.post(
        "/api/ai/notes/recognize",
        json={"image_url": uploaded["url"], "title_hint": "课堂笔记"},
    )
    payload = assert_ok(response)
    assert payload["ai"]["mode"] == "demo"
    assert payload["data"]["title"] == "课堂笔记"
    assert "没有调用视觉模型" in payload["data"]["markdown"]
    assert payload["data"]["confidence"] == 0.0

    remote = client.post(
        "/api/ai/tasks/recognize",
        json={"image_url": "https://example.com/homework.png"},
    )
    assert remote.status_code == 400
    assert remote.get_json()["error"]["code"] == "INVALID_IMAGE_URL"

    missing_image = client.post("/api/ai/tasks/recognize", json={})
    assert missing_image.status_code == 400


def test_essay_polish_sentence_grammar_demo(client, upload_image):
    essay = (
        "i think this book is very good. "
        "he go to school yesterday and I am agree with him becuase it is interesting"
    )
    payload = assert_ok(client.post("/api/ai/essay/review", json={"text": essay}))
    assert payload["ai"]["mode"] == "demo"
    data = payload["data"]
    assert data["overall"]["score"] > 0
    assert data["corrected_text"]
    assert data["corrections"]
    assert any(item["category"] == "拼写" for item in data["corrections"])
    assert all(item["certainty"] in {"certain", "review"} for item in data["corrections"])
    assert "演示" in payload["ai"]["notice"]

    image_review = assert_ok(
        client.post(
            "/api/ai/essay/review",
            json={"image_url": upload_image()["url"]},
        )
    )["data"]
    assert image_review["overall"]["level"] == "无法评分"
    assert image_review["warnings"]

    polished = assert_ok(
        client.post(
            "/api/ai/express/polish",
            json={"text": "I think this book is very good because it is interesting."},
        )
    )["data"]
    assert polished["simple"]["text"]
    assert polished["natural"]["text"]
    assert polished["advanced"]["text"]

    sentence = assert_ok(
        client.post(
            "/api/ai/sentence/analyze",
            json={"sentence": "The book that I bought yesterday is very interesting."},
        )
    )["data"]
    assert sentence["main_clause"]
    assert sentence["clauses"]
    assert sentence["caution"]

    grammar = assert_ok(
        client.post(
            "/api/ai/grammar/check",
            json={"sentence": "He go to school yesterday."},
        )
    )["data"]
    assert grammar["is_correct"] is False
    assert grammar["issues"]
    assert grammar["corrected_text"].lower().startswith("he goes")


def test_question_generation_grading_and_grade_analysis_demo(client):
    questions = assert_ok(
        client.post(
            "/api/ai/questions/generate",
            json={
                "subject": "数学",
                "topic": "二次函数",
                "difficulty": "medium",
                "count": 3,
            },
        )
    )["data"]
    assert len(questions["questions"]) == 3
    assert all(question["answer"] for question in questions["questions"])

    grading = assert_ok(
        client.post(
            "/api/ai/grading/assist",
            json={
                "question": "说明浮力方向。",
                "reference_answer": "浮力方向竖直向上。浮力大小等于排开液体重力。",
                "student_answer": "浮力向上。",
                "max_score": 10,
            },
        )
    )["data"]
    assert 0 <= grading["score"] <= 10
    assert grading["confidence"] == "low"
    assert grading["warnings"]

    client.post(
        "/api/grades",
        json={
            "subject": "数学",
            "exam_name": "月考",
            "score": 80,
            "max_score": 100,
            "exam_date": "2026-01-10",
        },
    )
    client.post(
        "/api/grades",
        json={
            "subject": "数学",
            "exam_name": "期中",
            "score": 88,
            "max_score": 100,
            "exam_date": "2026-02-10",
        },
    )
    analysis = assert_ok(client.post("/api/ai/grades/analyze", json={"range": "all"}))
    assert analysis["ai"]["mode"] == "demo"
    assert analysis["data"]["summary"]
    assert analysis["data"]["disclaimer"]


def test_note_ai_audit_graph_and_flashcards_demo(client, sample_note, upload_image):
    note_id = sample_note["id"]
    audit = assert_ok(client.post(f"/api/notes/{note_id}/audit", json={}))
    assert audit["ai"]["mode"] == "demo"
    assert audit["data"]["coverage_note"]
    assert audit["data"]["summary"]

    graph = assert_ok(client.post(f"/api/notes/{note_id}/graph", json={}))
    assert graph["ai"]["mode"] == "demo"
    assert graph["data"]["nodes"]
    assert graph["data"]["warnings"]

    cards = assert_ok(
        client.post(
            "/api/ai/flashcards/generate",
            json={"note_id": note_id, "count": 3},
        )
    )["data"]
    assert cards["cards"]
    assert cards["summary"]

    classified = assert_ok(
        client.post(
            "/api/ai/errors/classify",
            json={
                "question": "已知二次函数 y=ax²+bx+c 的顶点，求解析式。",
                "student_answer": "代入 x=0",
                "subject_hint": "数学",
            },
        )
    )["data"]
    assert classified["subject"] == "数学"
    assert classified["warnings"]
    assert classified["confidence"] == "low"


def test_ai_mode_off_returns_explicit_error(app_factory):
    app = app_factory(AI_DEMO_MODE="off")
    client = authenticate_client(app)
    response = client.post("/api/ai/express/polish", json={"text": "Hello world."})
    assert response.status_code == 503
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "AI_NOT_CONFIGURED"
    assert "AI_TEXT_API_KEY" in payload["error"]["message"]

    # A caller can explicitly opt into demo mode for exploration.
    response = client.post(
        "/api/ai/express/polish", json={"text": "Hello world.", "demo": True}
    )
    payload = assert_ok(response)
    assert payload["ai"]["mode"] == "demo"


def test_ai_json_parser_handles_code_fences_and_prose():
    parsed = AIService.extract_json_object(
        'Here is the result:\n```json\n{"tasks": [{"title": "练习"}], "warnings": []}\n```\nDone.'
    )
    assert parsed["tasks"][0]["title"] == "练习"

    parsed = AIService.extract_json_object('prefix {"answer": "ok", "nested": {"x": 1}} suffix')
    assert parsed["nested"]["x"] == 1

    try:
        AIService.extract_json_object("not json")
    except ValueError:
        pass
    else:
        raise AssertionError("invalid content should raise ValueError")
