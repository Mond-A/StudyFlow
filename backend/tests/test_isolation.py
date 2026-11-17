"""Cross-account isolation tests for records, associations and uploads."""

from __future__ import annotations

import io
import json
from datetime import date
from urllib.parse import parse_qs, urlsplit

from PIL import Image

PASSWORD = "isolation password 2026!"


def _image_bytes() -> io.BytesIO:
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), (230, 240, 255)).save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def _latest_token(app) -> str:
    outbox = app.extensions["studyflow_mail_outbox"]
    url = outbox[-1]["verification_url"]
    return parse_qs(urlsplit(url).query)["token"][0]


def _account(app, email: str):
    client = app.test_client()
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": PASSWORD, "display_name": email.split("@")[0]},
    )
    assert response.status_code == 201, response.get_json()
    token = _latest_token(app)
    assert client.get(f"/verify-email?token={token}").status_code == 302
    login = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.get_json()
    return client


def _upload(client):
    response = client.post(
        "/api/uploads",
        data={"image": (_image_bytes(), "isolation.png")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()["data"]


def test_accounts_cannot_read_modify_delete_or_reference_each_other(app):
    alice = _account(app, "alice-isolation@example.test")
    bob = _account(app, "bob-isolation@example.test")

    alice_upload = _upload(alice)
    alice_task = alice.post(
        "/api/tasks", json={"title": "alice-only task", "subject": "数学"}
    ).get_json()["data"]
    alice_grade = alice.post(
        "/api/grades",
        json={
            "subject": "数学",
            "exam_name": "alice exam",
            "score": 100,
            "max_score": 120,
            "exam_date": "2026-09-01",
        },
    ).get_json()["data"]
    alice_note = alice.post(
        "/api/notes",
        json={
            "title": "alice-only note",
            "subject": "数学",
            "content_markdown": "private",
            "source_image": alice_upload["url"],
        },
    ).get_json()["data"]
    alice_error = alice.post(
        "/api/errors",
        json={"subject": "数学", "question": "alice-only error"},
    ).get_json()["data"]
    alice_card = alice.post(
        "/api/flashcards",
        json={"front": "alice front", "back": "alice back", "note_id": alice_note["id"]},
    ).get_json()["data"]
    alice_session = alice.post(
        "/api/study/sessions",
        json={"subject": "数学", "duration_minutes": 25, "task_id": alice_task["id"]},
    ).get_json()["data"]["session"]
    assert alice.get(alice_upload["url"]).status_code == 200

    # Alice can read/modify her own records; the error API is list-only.
    assert alice.get(f"/api/tasks/{alice_task['id']}").status_code == 200
    assert alice.get(f"/api/notes/{alice_note['id']}").status_code == 200
    assert any(
        item["id"] == alice_error["id"]
        for item in alice.get("/api/errors").get_json()["data"]["errors"]
    )
    assert alice.patch(
        f"/api/tasks/{alice_task['id']}", json={"title": "alice renamed"}
    ).status_code == 200

    # Bob cannot read Alice's records or file.
    for path in (
        f"/api/tasks/{alice_task['id']}",
        f"/api/notes/{alice_note['id']}",
        alice_upload["url"],
    ):
        assert bob.get(path).status_code == 404, path
    assert not any(
        item["id"] == alice_error["id"]
        for item in bob.get("/api/errors").get_json()["data"]["errors"]
    )

    # Bob cannot modify or delete Alice's records.
    for method, path, kwargs in (
        ("patch", f"/api/tasks/{alice_task['id']}", {"json": {"title": "stolen"}}),
        ("delete", f"/api/tasks/{alice_task['id']}", {}),
        ("post", f"/api/tasks/{alice_task['id']}/start", {"json": {}}),
        ("post", f"/api/tasks/{alice_task['id']}/complete", {"json": {"actual_minutes": 1}}),
        ("post", f"/api/tasks/{alice_task['id']}/reopen", {"json": {}}),
        ("post", f"/api/notes/{alice_note['id']}/audit", {"json": {}}),
        ("post", f"/api/notes/{alice_note['id']}/graph", {"json": {}}),
        ("post", f"/api/flashcards/{alice_card['id']}/review", {"json": {"mastery_level": 1}}),
        ("patch", f"/api/grades/{alice_grade['id']}", {"json": {"score": 1}}),
        ("delete", f"/api/grades/{alice_grade['id']}", {}),
        ("patch", f"/api/notes/{alice_note['id']}", {"json": {"title": "stolen"}}),
        ("delete", f"/api/notes/{alice_note['id']}", {}),
        ("patch", f"/api/errors/{alice_error['id']}", {"json": {"question": "stolen"}}),
        ("delete", f"/api/errors/{alice_error['id']}", {}),
        ("patch", f"/api/flashcards/{alice_card['id']}", {"json": {"front": "stolen"}}),
        ("delete", f"/api/flashcards/{alice_card['id']}", {}),
        ("delete", f"/api/study/sessions/{alice_session['id']}", {}),
    ):
        assert getattr(bob, method)(path, **kwargs).status_code == 404, (method, path)

    # Bob cannot forge ownership via body fields.
    forged = bob.post(
        "/api/tasks",
        json={"title": "forged owner", "subject": "英语", "user_id": 1},
    )
    assert forged.status_code == 201
    forged_task = forged.get_json()["data"]
    assert any(
        item["id"] == forged_task["id"]
        for item in bob.get("/api/tasks").get_json()["data"]["tasks"]
    )
    assert not any(
        item["id"] == forged_task["id"]
        for item in alice.get("/api/tasks").get_json()["data"]["tasks"]
    )
    assert not any(
        item["title"] == "alice-only task"
        for item in bob.get("/api/tasks").get_json()["data"]["tasks"]
    )

    # Aggregate/read-model endpoints must not expose Alice's data.
    bob_export = bob.get("/api/export").get_json()
    assert "alice-only note" not in json.dumps(bob_export, ensure_ascii=False)
    bob_dashboard = bob.get("/api/dashboard").get_json()["data"]
    assert "alice-only task" not in json.dumps(bob_dashboard, ensure_ascii=False)
    bob_report = bob.get(f"/api/reports/daily?date={date.today().isoformat()}")
    assert bob_report.status_code == 200
    assert "alice-only note" not in bob_report.get_data(as_text=True)
    bob_sessions = bob.get("/api/study/sessions").get_json()["data"]["sessions"]
    assert not any(item["id"] == alice_session["id"] for item in bob_sessions)
    bob_cards = bob.get("/api/flashcards").get_json()["data"]["flashcards"]
    assert not any(item["id"] == alice_card["id"] for item in bob_cards)
    bob_notes = bob.get("/api/notes").get_json()["data"]["notes"]
    assert not any(item["id"] == alice_note["id"] for item in bob_notes)
    bob_settings = bob.get("/api/settings").get_json()["data"]
    assert bob_settings["user"]["email"] != "alice-isolation@example.test"

    # Bob cannot reference Alice's note/task/upload in nested records.
    assert bob.post(
        "/api/flashcards",
        json={"front": "cross", "back": "cross", "note_id": alice_note["id"]},
    ).status_code == 404
    assert bob.post(
        "/api/study/sessions",
        json={"subject": "数学", "duration_minutes": 20, "task_id": alice_task["id"]},
    ).status_code == 404
    assert bob.post(
        "/api/notes",
        json={"title": "cross", "source_image": alice_upload["url"]},
    ).status_code == 404
    assert bob.post(
        "/api/ai/notes/recognize", json={"image_url": alice_upload["url"]}
    ).status_code == 404
    assert bob.post(
        "/api/ai/tasks/recognize", json={"image_url": alice_upload["url"]}
    ).status_code == 404
    assert bob.post(
        "/api/ai/essay/review", json={"image_url": alice_upload["url"]}
    ).status_code == 404
    assert bob.post(
        "/api/ai/flashcards/generate", json={"note_id": alice_note["id"]}
    ).status_code == 404

    # Bob can upload and read his own file, while Alice cannot read Bob's file.
    bob_upload = _upload(bob)
    assert bob.get(bob_upload["url"]).status_code == 200
    assert alice.get(bob_upload["url"]).status_code == 404

    # Logout revokes the session immediately.
    bob.post("/api/auth/logout")
    assert bob.get("/api/tasks").status_code == 401
    assert bob.get("/api/meta").status_code == 401


def test_demo_loading_and_clearing_are_scoped_to_the_session(app):
    alice = _account(app, "alice-demo@example.test")
    bob = _account(app, "bob-demo@example.test")

    assert alice.post("/api/demo/load", json={}).status_code == 200
    assert alice.get("/api/demo").get_json()["data"]["loaded"] is True
    assert bob.get("/api/demo").get_json()["data"]["loaded"] is False

    bob_clear = bob.delete("/api/demo/clear")
    assert bob_clear.status_code == 200
    assert bob_clear.get_json()["data"]["cleared"] == 0
    assert alice.get("/api/demo").get_json()["data"]["loaded"] is True

    alice_clear = alice.delete("/api/demo/clear")
    assert alice_clear.status_code == 200
    assert alice_clear.get_json()["data"]["cleared"] > 0
    assert alice.get("/api/demo").get_json()["data"]["loaded"] is False
    assert bob.get("/api/demo").get_json()["data"]["loaded"] is False
