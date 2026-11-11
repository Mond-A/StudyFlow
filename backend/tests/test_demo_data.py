"""Demo seed/clear and export tests."""

from __future__ import annotations

from .conftest import assert_ok


def test_demo_load_populates_dashboard_and_clear_preserves_user_data(client):
    # A user-created task must survive clearing only demo data.
    own_task = assert_ok(
        client.post(
            "/api/tasks",
            json={"title": "我自己创建的任务", "subject": "数学", "estimated_minutes": 20},
        ),
        expected_status=201,
    )["data"]
    empty_dashboard = assert_ok(client.get("/api/dashboard"))["data"]
    assert [task["id"] for task in empty_dashboard["today_tasks"]] == [own_task["id"]]
    assert empty_dashboard["has_fallback_tasks"] is True
    assert empty_dashboard["stats"]["achievements_unlocked"] == 0

    loaded = assert_ok(client.post("/api/demo/load", json={}))["data"]
    assert loaded["created"] > 0
    assert loaded["counts"]["tasks"] > 0
    assert loaded["counts"]["notes"] > 0
    assert loaded["counts"]["flashcards"] > 0

    dashboard = assert_ok(client.get("/api/dashboard"))["data"]
    assert dashboard["today_tasks"]
    assert dashboard["recent_grades"]
    assert dashboard["recent_sessions"]
    assert dashboard["stats"]["study_days"] > 0

    notes = assert_ok(client.get("/api/notes"))["data"]["notes"]
    assert len(notes) >= 3
    report = assert_ok(client.get("/api/reports/daily"))["data"]
    assert report["study"]["total_minutes"] > 0

    cleared = assert_ok(client.delete("/api/demo/clear"))["data"]
    assert cleared["cleared"] > 0

    tasks = assert_ok(client.get("/api/tasks"))["data"]["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["id"] == own_task["id"]

    notes_after = assert_ok(client.get("/api/notes"))["data"]["notes"]
    assert notes_after == []
    achievements_after = assert_ok(client.get("/api/achievements"))["data"]
    assert achievements_after["unlocked_count"] == 0
    assert assert_ok(client.get("/api/demo"))["data"]["loaded"] is False

    # Re-loading explicitly works after a clear.
    loaded_again = assert_ok(client.post("/api/demo/load", json={}))["data"]
    assert loaded_again["created"] > 0
    assert assert_ok(client.get("/api/demo"))["data"]["loaded"] is True


def test_export_contains_all_major_tables(client, sample_note):
    assert_ok(
        client.post(
            "/api/tasks",
            json={"title": "导出测试任务", "subject": "英语", "estimated_minutes": 20},
        ),
        expected_status=201,
    )
    response = client.get("/api/export")
    assert response.status_code == 200
    assert "attachment" in response.headers["Content-Disposition"]
    import json

    payload = json.loads(response.get_data(as_text=True))
    assert payload["app"]["name"] == "StudyFlow"
    assert payload["tasks"]
    assert payload["notes"]
    assert payload["user"]["username"] == "student"
    assert "AI_TEXT_API_KEY" not in json.dumps(payload)
