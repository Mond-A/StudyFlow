"""Security boundary tests between the guest SPA and server authentication."""

from __future__ import annotations

import re


def _guest_token(response) -> str:
    body = response.get_data(as_text=True)
    match = re.search(r'name="csrf_token" value="([^"]+)"', body)
    assert match, body
    return match.group(1)


def test_get_guest_shows_confirmation_without_clearing_session(client):
    assert client.get("/api/meta").status_code == 200
    with client.session_transaction() as sess:
        assert sess.get("authenticated") is True
        assert sess.get("user_id") == 1

    guest = client.get("/guest")
    assert guest.status_code == 200
    body = guest.get_data(as_text=True)
    assert "进入访客模式" in body
    assert 'method="post"' in body
    token = _guest_token(guest)

    # GET is side-effect free: the formal session is still valid.
    with client.session_transaction() as sess:
        assert sess.get("authenticated") is True
        assert sess.get("user_id") == 1
    assert client.get("/api/meta").status_code == 200

    switched = client.post("/guest", data={"csrf_token": token})
    assert switched.status_code == 200
    body = switched.get_data(as_text=True)
    assert "window.__STUDYFLOW_GUEST__ = true" in body
    assert "window.__STUDYFLOW_GUEST_SWITCHED__ = true" in body

    with client.session_transaction() as sess:
        assert "authenticated" not in sess
        assert "user_id" not in sess

    # The shared browser cookie no longer authenticates direct API requests.
    assert client.get("/api/meta").status_code == 401
    assert client.get("/api/tasks").status_code == 401
    assert client.post("/api/ai/essay/review", json={"text": "test"}).status_code == 401
    assert client.post("/api/uploads", data={}, content_type="multipart/form-data").status_code == 401
    assert client.get("/").status_code == 302


def test_guest_switch_rejects_missing_invalid_and_cross_origin_requests(client):
    guest = client.get("/guest")
    token = _guest_token(guest)
    assert client.get("/api/meta").status_code == 200

    missing = client.post("/guest", data={})
    assert missing.status_code == 403
    assert client.get("/api/meta").status_code == 200

    invalid = client.post("/guest", data={"csrf_token": "not-a-valid-token"})
    assert invalid.status_code == 403
    assert client.get("/api/meta").status_code == 200

    cross_origin = client.post(
        "/guest",
        data={"csrf_token": token},
        headers={"Origin": "https://evil.example"},
    )
    assert cross_origin.status_code == 403
    assert client.get("/api/meta").status_code == 200

    # A same-origin, valid-token request is the only successful switch.
    switched = client.post("/guest", data={"csrf_token": token})
    assert switched.status_code == 200
    assert client.get("/api/meta").status_code == 401


def test_guest_mode_has_no_direct_server_api_data_path(anonymous_client):
    assert anonymous_client.get("/api/tasks").status_code == 401
    assert anonymous_client.get("/api/grades/analytics").status_code == 401
    assert anonymous_client.get("/api/notes").status_code == 401
    assert anonymous_client.get("/api/study/sessions").status_code == 401
    assert anonymous_client.get("/api/flashcards").status_code == 401
    assert anonymous_client.get("/api/errors").status_code == 401
    assert anonymous_client.get("/api/export").status_code == 401
    assert anonymous_client.post("/api/guest/import", json={}).status_code == 401
    # A raw upload URL without a session is not served as an image.
    assert anonymous_client.get("/uploads/not-a-real-file.png").status_code == 302


def test_direct_ai_requests_are_denied_without_a_verified_session(anonymous_client):
    requests = (
        ("get", "/api/ai/status", {}),
        ("post", "/api/ai/tasks/recognize", {"json": {"image_url": "/uploads/whatever.png"}}),
        ("post", "/api/ai/grades/analyze", {"json": {}}),
        ("post", "/api/ai/essay/review", {"json": {"text": "test"}}),
        ("post", "/api/ai/flashcards/generate", {"json": {"markdown": "test"}}),
    )
    for method, path, kwargs in requests:
        response = getattr(anonymous_client, method)(path, **kwargs)
        assert response.status_code == 401, (path, response.status_code)
        assert response.get_json()["error"]["code"] == "AUTH_REQUIRED"


def test_guest_route_is_public_but_does_not_create_a_server_session(anonymous_client):
    guest = anonymous_client.get("/guest")
    assert guest.status_code == 200
    token = _guest_token(guest)
    with anonymous_client.session_transaction() as sess:
        assert "authenticated" not in sess
        assert "user_id" not in sess
    switched = anonymous_client.post("/guest", data={"csrf_token": token})
    assert switched.status_code == 200
    assert "window.__STUDYFLOW_GUEST__ = true" in switched.get_data(as_text=True)
    assert anonymous_client.get("/api/meta").status_code == 401
