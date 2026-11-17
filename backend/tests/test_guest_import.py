"""Guest-to-account import tests using the test database only."""

from __future__ import annotations

import sqlite3
from urllib.parse import parse_qs, urlsplit

PASSWORD = "guest import password 2026!"


def _account(app, email: str):
    client = app.test_client()
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": PASSWORD, "display_name": email.split("@")[0]},
    )
    assert response.status_code == 201, response.get_json()
    url = app.extensions["studyflow_mail_outbox"][-1]["verification_url"]
    token = parse_qs(urlsplit(url).query)["token"][0]
    assert client.get(f"/verify-email?token={token}").status_code == 302
    assert client.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    ).status_code == 200
    return client


def _payload(batch="guest-batch-1", user_id=None):
    return {
        "client_batch_id": batch,
        "device_id": "browser-test-device",
        "user_id": user_id,
        "data": {
            "tasks": [
                {
                    "local_uid": "task-1",
                    "title": "guest task",
                    "subject": "数学",
                    "estimated_minutes": 30,
                }
            ],
            "grades": [
                {
                    "local_uid": "grade-1",
                    "subject": "数学",
                    "exam_name": "guest exam",
                    "score": 95,
                    "max_score": 120,
                    "exam_date": "2026-10-01",
                }
            ],
            "notes": [
                {
                    "local_uid": "note-1",
                    "title": "guest note",
                    "subject": "数学",
                    "content_markdown": "guest content",
                }
            ],
            "study_sessions": [
                {
                    "local_uid": "session-1",
                    "local_task_uid": "task-1",
                    "subject": "数学",
                    "duration_minutes": 25,
                    "started_at": "2026-10-01T18:00:00+08:00",
                }
            ],
            "flashcards": [
                {
                    "local_uid": "card-1",
                    "local_note_uid": "note-1",
                    "front": "guest front",
                    "back": "guest back",
                }
            ],
            "errors": [
                {
                    "local_uid": "error-1",
                    "subject": "数学",
                    "question": "guest question",
                }
            ],
        },
    }


def _counts(app):
    conn = sqlite3.connect(app.config["DATABASE_PATH"])
    try:
        tables = ("tasks", "grades", "notes", "study_sessions", "flashcards", "error_records")
        return {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables}
    finally:
        conn.close()


def test_guest_import_requires_login_and_uses_session_user(app):
    anonymous = app.test_client()
    assert anonymous.post("/api/guest/import", json=_payload()).status_code == 401

    alice = _account(app, "alice-import@example.test")
    response = alice.post("/api/guest/import", json=_payload(user_id=999))
    assert response.status_code == 200, response.get_json()
    data = response.get_json()["data"]
    assert data["total_imported"] == 6
    assert all(value["imported"] == 1 for value in data["counts"].values())

    # The forged target user_id was ignored.
    conn = sqlite3.connect(app.config["DATABASE_PATH"])
    try:
        task_user = conn.execute("SELECT user_id FROM tasks WHERE title='guest task'").fetchone()[0]
        alice_id = conn.execute("SELECT user_id FROM auth_accounts WHERE email='alice-import@example.test'").fetchone()[0]
    finally:
        conn.close()
    assert task_user == alice_id


def test_guest_import_is_idempotent_and_scoped(app):
    alice = _account(app, "alice-idempotent@example.test")
    before = _counts(app)
    first = alice.post("/api/guest/import", json=_payload("same-batch"))
    assert first.status_code == 200
    after_first = _counts(app)
    assert all(after_first[key] == before[key] + 1 for key in ("tasks", "grades", "notes", "study_sessions", "flashcards", "error_records"))

    second = alice.post("/api/guest/import", json=_payload("same-batch"))
    assert second.status_code == 200
    assert second.get_json()["data"]["already_imported"] is True
    after_second = _counts(app)
    assert after_second == after_first

    bob = _account(app, "bob-idempotent@example.test")
    bob_import = bob.post("/api/guest/import", json=_payload("bob-batch", user_id=1))
    assert bob_import.status_code == 200
    assert bob_import.get_json()["data"]["total_imported"] == 6
    listed = bob.get("/api/tasks").get_json()["data"]["tasks"]
    assert any(item["title"] == "guest task" for item in listed)
    alice_listed = alice.get("/api/tasks").get_json()["data"]["tasks"]
    assert sum(1 for item in alice_listed if item["title"] == "guest task") == 1


def test_failed_guest_import_rolls_back_entire_batch(app):
    alice = _account(app, "alice-rollback@example.test")
    before = _counts(app)
    payload = _payload("rollback-batch")
    payload["data"]["grades"].append(
        {
            "local_uid": "bad-grade",
            "subject": "数学",
            "exam_name": "bad",
            "score": 1,
            "max_score": 120,
            "exam_date": "not-a-date",
        }
    )
    response = alice.post("/api/guest/import", json=payload)
    assert response.status_code == 400
    assert _counts(app) == before
    conn = sqlite3.connect(app.config["DATABASE_PATH"])
    try:
        batch = conn.execute(
            "SELECT COUNT(*) FROM guest_import_batches WHERE client_batch_id='rollback-batch'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert batch == 0
