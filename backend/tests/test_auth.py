"""Authentication and access-control regression tests."""

from __future__ import annotations

import time

import pytest

from backend.auth import reset_login_limits
from .conftest import TEST_PASSWORD, authenticate_client


def _login(client, password: str = TEST_PASSWORD, next_path: str = "/"):
    return client.post(
        "/api/auth/login",
        json={"password": password, "next": next_path},
    )


def test_login_page_is_public_and_root_is_protected(anonymous_client):
    login = anonymous_client.get("/login")
    assert login.status_code == 200
    body = login.get_data(as_text=True)
    assert "登录 StudyFlow" in body
    assert "login.css" in body
    assert "password" in body

    css = anonymous_client.get("/css/login.css")
    assert css.status_code == 200

    root = anonymous_client.get("/")
    assert root.status_code == 302
    assert "/login" in root.headers["Location"]

    index = anonymous_client.get("/index.html")
    assert index.status_code == 302


def test_unauthenticated_api_returns_json_401(anonymous_client):
    for method, path, kwargs in (
        ("get", "/api/health", {}),
        ("get", "/api/meta", {}),
        ("get", "/api/settings", {}),
        ("post", "/api/tasks", {"json": {"title": "blocked", "subject": "数学"}}),
        ("delete", "/api/tasks/1", {}),
        ("get", "/api/does-not-exist", {}),
    ):
        response = getattr(anonymous_client, method)(path, **kwargs)
        assert response.status_code == 401, (path, response.status_code)
        assert response.is_json, path
        payload = response.get_json()
        assert payload["ok"] is False
        assert payload["error"]["code"] == "AUTH_REQUIRED"
        assert "text/html" not in response.content_type


def test_login_limit_is_shared_across_worker_clients(app_factory):
    """The limiter must use shared state, not a per-process counter."""
    app = app_factory(LOGIN_MAX_ATTEMPTS=2)
    reset_login_limits(app)
    first_worker = app.test_client()
    second_worker = app.test_client()

    assert _login(first_worker, "definitely-wrong").status_code == 401
    assert _login(second_worker, "definitely-wrong").status_code == 401
    blocked = _login(first_worker, "definitely-wrong")
    assert blocked.status_code == 429
    assert blocked.get_json()["error"]["code"] == "LOGIN_RATE_LIMITED"


def test_correct_password_login_session_and_logout(anonymous_client):
    with anonymous_client.session_transaction() as sess:
        sess["pre_login"] = "must-disappear"

    response = _login(anonymous_client, next_path="/#/settings")
    assert response.status_code == 200
    assert response.get_json()["ok"] is True
    assert response.get_json()["data"]["redirect"] == "/#/settings"

    with anonymous_client.session_transaction() as sess:
        assert sess["authenticated"] is True
        assert sess["auth_nonce"]
        assert "pre_login" not in sess

    assert anonymous_client.get("/api/meta").status_code == 200
    assert anonymous_client.get("/").status_code == 200

    logout = anonymous_client.post("/api/auth/logout", json={})
    assert logout.status_code == 200
    assert anonymous_client.get("/api/meta").status_code == 401
    assert anonymous_client.get("/").status_code == 302


def test_wrong_password_has_clear_error_and_is_rate_limited(app, anonymous_client):
    reset_login_limits(app)
    for _ in range(5):
        response = _login(anonymous_client, "definitely-wrong")
        assert response.status_code == 401
        assert response.get_json()["error"]["code"] == "INVALID_CREDENTIALS"

    blocked = _login(anonymous_client, "definitely-wrong")
    assert blocked.status_code == 429
    assert blocked.get_json()["error"]["code"] == "LOGIN_RATE_LIMITED"
    assert int(blocked.headers["Retry-After"]) > 0

    # A correct password does not bypass an already locked IP/window.
    still_blocked = _login(anonymous_client)
    assert still_blocked.status_code == 429

    reset_login_limits(app)
    assert _login(anonymous_client).status_code == 200


def test_form_login_fallback_and_wrong_form_redirect(anonymous_client):
    failed = anonymous_client.post(
        "/login",
        data={"password": "wrong-password", "next": "/"},
        follow_redirects=False,
    )
    assert failed.status_code == 302
    assert "error=invalid" in failed.headers["Location"]

    success = anonymous_client.post(
        "/login",
        data={"password": TEST_PASSWORD, "next": "/"},
        follow_redirects=False,
    )
    assert success.status_code == 302
    assert success.headers["Location"] == "/"
    assert anonymous_client.get("/api/meta").status_code == 200


def test_session_expiry_requires_new_login(app, anonymous_client):
    assert _login(anonymous_client).status_code == 200
    with anonymous_client.session_transaction() as sess:
        sess["auth_at"] = int(time.time()) - 60 * 60 * 24 * 2

    response = anonymous_client.get("/api/meta")
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "AUTH_REQUIRED"


def test_cross_site_write_is_rejected_and_data_is_not_modified(client, anonymous_client):
    blocked = anonymous_client.post(
        "/api/tasks",
        json={"title": "blocked", "subject": "数学"},
        headers={"Origin": "https://evil.example"},
    )
    assert blocked.status_code == 401

    authenticated = authenticate_client(client.application)
    cross_site = authenticated.post(
        "/api/tasks",
        json={"title": "blocked", "subject": "数学"},
        headers={"Origin": "https://evil.example"},
    )
    assert cross_site.status_code == 403
    assert cross_site.get_json()["error"]["code"] == "CSRF_REJECTED"

    tasks = authenticated.get("/api/tasks").get_json()["data"]["tasks"]
    assert all(task["title"] != "blocked" for task in tasks)


def test_login_page_cross_site_origin_is_rejected(anonymous_client):
    response = anonymous_client.post(
        "/api/auth/login",
        json={"password": TEST_PASSWORD},
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 403
    assert response.is_json
    assert response.get_json()["error"]["code"] == "CSRF_REJECTED"


def test_secure_cookie_flags(app_factory, anonymous_client):
    assert _login(anonymous_client).status_code == 200
    cookie = anonymous_client.get("/api/meta").headers.get("Set-Cookie")
    assert cookie is not None
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie
    assert "Secure" not in cookie

    secure_app = app_factory(SESSION_COOKIE_SECURE=True)
    secure_client = secure_app.test_client()
    assert _login(secure_client).status_code == 200
    secure_cookie = secure_client.get("/api/meta").headers.get("Set-Cookie")
    assert "Secure" in secure_cookie


def test_security_config_fails_closed(app_factory):
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        app_factory(SECRET_KEY="short")
    with pytest.raises(RuntimeError, match="STUDYFLOW_PASSWORD_HASH"):
        app_factory(STUDYFLOW_PASSWORD_HASH="")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        app_factory(SECRET_KEY="please-change-this-to-a-random-string")


def test_login_page_static_assets_do_not_require_session(anonymous_client):
    for path in ("/assets/logo.svg", "/css/fluent/studyflow-fluent-tokens.css", "/js/login.js"):
        response = anonymous_client.get(path)
        assert response.status_code == 200, path
