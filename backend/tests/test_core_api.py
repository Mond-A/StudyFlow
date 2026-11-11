"""Core API tests: health, tasks, planning, grades, notes, sessions, reports."""

from __future__ import annotations

from datetime import date, timedelta

from backend.utils.timeutils import today_iso
from .conftest import assert_ok


def test_health_meta_and_frontend(client):
    assert_ok(client.get("/api/health"))
    meta = assert_ok(client.get("/api/meta"))["data"]
    assert meta["app"]["name"] == "StudyFlow"
    assert meta["user"]["username"] == "student"
    assert meta["ai"]["text"]["effective_mode"] == "demo"
    assert meta["demo"]["loaded"] is False

    index = client.get("/")
    assert index.status_code == 200
    assert "StudyFlow" in index.get_data(as_text=True)
    css = client.get("/css/base.css")
    assert css.status_code == 200
    assert b"--primary" in css.data


def test_api_404_and_validation_error_shape(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "NOT_FOUND"

    response = client.post("/api/tasks", json={"subject": "数学"})
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "VALIDATION_ERROR"

    response = client.post("/api/tasks", data="not-json", content_type="text/plain")
    assert response.status_code == 415
    assert response.get_json()["ok"] is False


def test_task_crud_and_status_flow(client):
    created = assert_ok(
        client.post(
            "/api/tasks",
            json={
                "title": "订正英语错题",
                "subject": "英语",
                "description": "整理 Unit 4 错题",
                "due_date": today_iso(),
                "estimated_minutes": 35,
                "difficulty": 4,
                "priority": 1,
            },
        ),
        expected_status=201,
    )["data"]
    task_id = created["id"]
    assert created["status"] == "pending"
    assert created["is_overdue"] is False

    listed = assert_ok(client.get("/api/tasks"))["data"]
    assert any(item["id"] == task_id for item in listed["tasks"])
    assert listed["counts"]["pending"] == 1

    updated = assert_ok(
        client.patch(f"/api/tasks/{task_id}", json={"estimated_minutes": 50, "priority": 2})
    )["data"]
    assert updated["estimated_minutes"] == 50
    assert updated["priority"] == 2

    started = assert_ok(client.post(f"/api/tasks/{task_id}/start", json={}))["data"]
    assert started["status"] == "in_progress"

    completed = assert_ok(
        client.post(f"/api/tasks/{task_id}/complete", json={"actual_minutes": 42})
    )["data"]
    assert completed["task"]["status"] == "completed"
    assert completed["task"]["actual_minutes"] == 42
    assert completed["task"]["completed_at"]
    assert any(
        achievement["code"] == "first_task"
        for achievement in completed["unlocked_achievements"]
    )

    reopened = assert_ok(client.post(f"/api/tasks/{task_id}/reopen", json={}))["data"]
    assert reopened["status"] == "pending"
    assert reopened["completed_at"] is None

    assert_ok(client.delete(f"/api/tasks/{task_id}"))
    assert client.get(f"/api/tasks/{task_id}").status_code == 404


def test_task_plan_preview_and_apply(client):
    today = date.fromisoformat(today_iso())
    for index, title in enumerate(["高优先级数学作业", "英语阅读", "物理复习"]):
        assert_ok(
            client.post(
                "/api/tasks",
                json={
                    "title": title,
                    "subject": ["数学", "英语", "物理"][index],
                    "estimated_minutes": 30 + index * 15,
                    "difficulty": 2 + index,
                    "priority": 1 if index == 0 else 2,
                    "due_date": (today + timedelta(days=index)).isoformat(),
                },
            ),
            expected_status=201,
        )

    preview = assert_ok(
        client.post(
            "/api/tasks/plan/preview",
            json={
                "plan_date": today.isoformat(),
                "start_time": "19:00",
                "available_minutes": 60,
            },
        )
    )["data"]
    assert preview["schedule"], preview
    assert preview["scheduled_minutes"] <= 60
    assert preview["schedule"][0]["start_time"] == "19:00"
    assert preview["schedule"][0]["planned_minutes"] > 0

    applied = assert_ok(
        client.post(
            "/api/tasks/plan/apply",
            json={
                "plan_date": today.isoformat(),
                "schedule": [
                    {
                        "task_id": item["task_id"],
                        "start_time": item["start_time"],
                        "planned_minutes": item["planned_minutes"],
                    }
                    for item in preview["schedule"]
                ],
            },
        )
    )["data"]
    assert applied["applied_count"] == len(preview["schedule"])
    tasks = assert_ok(client.get("/api/tasks"))["data"]["tasks"]
    planned = [task for task in tasks if task["planned_date"] == today.isoformat()]
    assert planned
    assert all(task["planned_start"] for task in planned)


def test_grades_crud_and_analytics(client):
    today = date.fromisoformat(today_iso())
    records = [
        ("数学", "单元测", 82, 100, today - timedelta(days=30)),
        ("数学", "期中", 91, 100, today - timedelta(days=10)),
        ("英语", "单元测", 78, 100, today - timedelta(days=25)),
        ("物理", "月考", 64, 80, today - timedelta(days=5)),
    ]
    ids = []
    for subject, name, score, max_score, exam_day in records:
        item = assert_ok(
            client.post(
                "/api/grades",
                json={
                    "subject": subject,
                    "exam_name": name,
                    "score": score,
                    "max_score": max_score,
                    "exam_date": exam_day.isoformat(),
                },
            ),
            expected_status=201,
        )["data"]
        ids.append(item["id"])

    analytics = assert_ok(client.get("/api/grades/analytics?range=90"))["data"]
    assert analytics["kpis"]["exam_count"] == 4
    assert len(analytics["subject_series"]) == 3
    assert analytics["overall_series"]
    assert analytics["kpis"]["best_subject"] is not None

    updated = assert_ok(
        client.put(
            f"/api/grades/{ids[0]}",
            json={"score": 85, "notes": "订正完成"},
        )
    )["data"]
    assert updated["score"] == 85
    assert updated["percentage"] == 85.0

    invalid = client.put(f"/api/grades/{ids[0]}", json={"score": 200})
    assert invalid.status_code == 400
    assert invalid.get_json()["ok"] is False

    filtered = assert_ok(client.get("/api/grades/analytics?subject=数学&range=90"))["data"]
    assert {item["subject"] for item in filtered["records"]} == {"数学"}

    assert_ok(client.delete(f"/api/grades/{ids[1]}"))
    remaining = assert_ok(client.get("/api/grades/analytics?range=all"))["data"]
    assert remaining["kpis"]["exam_count"] == 3


def test_notes_crud_audit_and_graph(client, sample_note):
    note_id = sample_note["id"]
    fetched = assert_ok(client.get(f"/api/notes/{note_id}"))["data"]
    assert "\\frac" in fetched["content_markdown"]
    original = fetched["content_markdown"]

    audit_response = client.post(f"/api/notes/{note_id}/audit", json={})
    audit_payload = assert_ok(audit_response)
    assert audit_payload["ai"]["mode"] == "demo"
    assert "corrections" in audit_payload["data"]
    saved = assert_ok(client.get(f"/api/notes/{note_id}"))["data"]
    assert saved["content_markdown"] == original
    assert saved["audit_report"] is not None

    graph_response = client.post(f"/api/notes/{note_id}/graph", json={})
    graph_payload = assert_ok(graph_response)
    assert graph_payload["ai"]["mode"] == "demo"
    graph = graph_payload["data"]
    assert graph["nodes"]
    node_ids = {node["id"] for node in graph["nodes"]}
    assert all(edge["source"] in node_ids and edge["target"] in node_ids for edge in graph["edges"])

    stored_graph = assert_ok(client.get(f"/api/notes/{note_id}/graph"))["data"]
    assert len(stored_graph["nodes"]) == len(graph["nodes"])

    updated = assert_ok(
        client.put(f"/api/notes/{note_id}", json={"title": "更新后的笔记标题"})
    )["data"]
    assert updated["title"] == "更新后的笔记标题"

    invalid_image = client.put(
        f"/api/notes/{note_id}", json={"source_image": "javascript:alert(1)"}
    )
    assert invalid_image.status_code == 400
    assert invalid_image.get_json()["error"]["code"] == "INVALID_SOURCE_IMAGE"

    assert_ok(client.delete(f"/api/notes/{note_id}"))
    assert client.get(f"/api/notes/{note_id}").status_code == 404


def test_study_sessions_reports_and_achievements(client, sample_task):
    session = assert_ok(
        client.post(
            "/api/study/sessions",
            json={
                "subject": "数学",
                "duration_minutes": 25,
                "session_type": "pomodoro",
                "task_id": sample_task["id"],
                "note": "专注练习",
            },
        ),
        expected_status=201,
    )["data"]
    assert session["session"]["duration_minutes"] == 25
    assert any(
        achievement["code"] == "focus_first"
        for achievement in session["unlocked_achievements"]
    )

    sessions = assert_ok(client.get("/api/study/sessions?date=" + today_iso()))["data"]
    assert len(sessions["sessions"]) == 1
    assert sessions["summary"]["today_minutes"] == 25

    stats = assert_ok(client.get("/api/study/stats"))["data"]
    assert stats["today_minutes"] == 25
    assert stats["by_subject"][0]["subject"] == "数学"

    report = assert_ok(client.get("/api/reports/daily"))["data"]
    assert report["study"]["total_minutes"] == 25
    assert report["date"] == today_iso()
    assert report["suggestions"]

    achievements = assert_ok(client.get("/api/achievements"))["data"]
    assert achievements["unlocked_count"] >= 1
    assert len(achievements["items"]) == 12

    assert_ok(client.delete(f"/api/study/sessions/{session['session']['id']}"))


def test_flashcards_and_error_records(client, sample_note):
    card = assert_ok(
        client.post(
            "/api/flashcards",
            json={
                "front": "对称轴公式？",
                "back": "$x=-\\frac{b}{2a}$",
                "subject": "数学",
                "note_id": sample_note["id"],
            },
        ),
        expected_status=201,
    )["data"]
    assert card["is_due"] is True
    assert card["mastery_level"] == 0

    reviewed = assert_ok(
        client.post(f"/api/flashcards/{card['id']}/review", json={"rating": 5})
    )["data"]
    assert reviewed["flashcard"]["mastery_level"] == 1
    assert reviewed["flashcard"]["next_review_date"] > today_iso()
    assert reviewed["flashcard"]["is_due"] is False

    error = assert_ok(
        client.post(
            "/api/errors",
            json={
                "subject": "数学",
                "question": "求二次函数顶点。",
                "student_answer": "直接代 x=0",
                "correct_answer": "使用顶点公式",
                "knowledge_points": ["二次函数", "顶点"],
                "mastery": "new",
            },
        ),
        expected_status=201,
    )["data"]
    assert error["knowledge_points"] == ["二次函数", "顶点"]

    updated = assert_ok(
        client.put(f"/api/errors/{error['id']}", json={"mastery": "mastered"})
    )["data"]
    assert updated["mastery"] == "mastered"

    listed = assert_ok(client.get("/api/errors"))["data"]
    assert listed["counts"]["mastered"] == 1

    assert_ok(client.delete(f"/api/errors/{error['id']}"))
    assert_ok(client.delete(f"/api/flashcards/{card['id']}"))


def test_settings_update(client):
    payload = assert_ok(
        client.put(
            "/api/settings",
            json={
                "display_name": "小夏",
                "daily_goal_minutes": 150,
                "pomodoro_minutes": 30,
                "short_break_minutes": 6,
                "long_break_minutes": 20,
                "avatar_color": "#0D9488",
            },
        )
    )["data"]
    assert payload["user"]["display_name"] == "小夏"
    assert payload["user"]["daily_goal_minutes"] == 150
    assert payload["user"]["avatar_color"] == "#0d9488"

    invalid = client.put("/api/settings", json={"display_name": "  "})
    assert invalid.status_code == 400
    assert invalid.get_json()["ok"] is False
