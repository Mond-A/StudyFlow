"""Email account registration, verification and session-binding tests."""

from __future__ import annotations

import sqlite3
from urllib.parse import parse_qs, urlsplit

from backend.auth import reset_login_limits

PASSWORD = "correct horse battery staple 2026"


def _latest_token(app) -> str:
    outbox = app.extensions["studyflow_mail_outbox"]
    assert outbox, "console mail backend should have captured a verification message"
    url = outbox[-1]["verification_url"]
    return parse_qs(urlsplit(url).query)["token"][0]


def _register(client, email, password=PASSWORD, display_name="测试同学"):
    return client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": display_name},
    )


def _verify(client, token):
    return client.get(f"/verify-email?token={token}")


def _login(client, email, password=PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_register_hashes_password_and_verification_is_required(app, anonymous_client):
    reset_login_limits(app)
    response = _register(anonymous_client, "Alice@Example.test", display_name="小艾")
    assert response.status_code == 201, response.get_json()
    assert response.get_json()["data"]["email"] == "alice@example.test"

    token = _latest_token(app)
    conn = sqlite3.connect(app.config["DATABASE_PATH"])
    try:
        account = conn.execute(
            "SELECT email, password_hash, email_verified_at FROM auth_accounts"
        ).fetchone()
        token_row = conn.execute(
            "SELECT token_hash FROM email_verification_tokens"
        ).fetchone()
    finally:
        conn.close()
    assert account[0] == "alice@example.test"
    assert account[1] != PASSWORD
    assert account[1].startswith("scrypt:")
    assert account[2] is None
    assert token_row[0] != token

    login = _login(anonymous_client, "alice@example.test")
    assert login.status_code == 403
    assert login.get_json()["error"]["code"] == "EMAIL_NOT_VERIFIED"

    verified = _verify(anonymous_client, token)
    assert verified.status_code == 302
    assert verified.headers["Location"].endswith("/login?verified=1")

    login = _login(anonymous_client, "alice@example.test")
    assert login.status_code == 200, login.get_json()
    assert login.get_json()["data"]["email"] == "alice@example.test"
    with anonymous_client.session_transaction() as sess:
        assert sess["authenticated"] is True
        assert sess["user_id"] > 1
        assert sess["account_id"] > 0


def test_duplicate_email_wrong_password_and_token_reuse(app, anonymous_client):
    assert _register(anonymous_client, "bob@example.test").status_code == 201
    duplicate = _register(anonymous_client, "BOB@example.test")
    assert duplicate.status_code == 409
    assert duplicate.get_json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"

    wrong = _login(anonymous_client, "bob@example.test", "not-the-password")
    assert wrong.status_code == 401
    assert wrong.get_json()["error"]["code"] == "INVALID_CREDENTIALS"

    token = _latest_token(app)
    assert _verify(anonymous_client, token).headers["Location"].endswith("verified=1")
    reused = _verify(anonymous_client, token)
    assert reused.headers["Location"].endswith("verified=0")

    missing = _login(anonymous_client, "nobody@example.test", PASSWORD)
    assert missing.status_code == 401
    assert missing.get_json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_expired_token_and_resend(app, anonymous_client):
    assert _register(anonymous_client, "carol@example.test").status_code == 201
    token = _latest_token(app)
    conn = sqlite3.connect(app.config["DATABASE_PATH"])
    try:
        conn.execute(
            "UPDATE email_verification_tokens SET expires_at = '2000-01-01T00:00:00+00:00'"
        )
        conn.commit()
    finally:
        conn.close()
    expired = _verify(anonymous_client, token)
    assert expired.status_code == 302
    assert expired.headers["Location"].endswith("verified=0")

    resent = anonymous_client.post(
        "/api/auth/resend-verification", json={"email": "carol@example.test"}
    )
    assert resent.status_code == 200
    new_token = _latest_token(app)
    assert new_token != token
    assert _verify(anonymous_client, new_token).headers["Location"].endswith("verified=1")


def test_logout_clears_session_and_session_binds_user_data(app):
    alice = app.test_client()
    assert _register(alice, "a@example.test", display_name="A").status_code == 201
    alice_token = _latest_token(app)
    _verify(alice, alice_token)
    assert _login(alice, "a@example.test").status_code == 200
    created = alice.post("/api/tasks", json={"title": "A-only", "subject": "数学"})
    assert created.status_code == 201, created.get_json()
    with alice.session_transaction() as sess:
        assert sess["user_id"] > 1
        assert sess["account_id"] > 0
    alice.post("/api/auth/logout")
    assert alice.get("/api/meta").status_code == 401

    bob = app.test_client()
    assert _register(bob, "b@example.test", display_name="B").status_code == 201
    bob_token = _latest_token(app)
    _verify(bob, bob_token)
    assert _login(bob, "b@example.test").status_code == 200
    listed = bob.get("/api/tasks")
    assert listed.status_code == 200, listed.get_json()
    titles = [item["title"] for item in listed.get_json()["data"]["tasks"]]
    assert "A-only" not in titles


def test_registration_validation_and_console_backend(app, anonymous_client):
    bad_email = _register(anonymous_client, "not-an-email")
    assert bad_email.status_code == 400
    short_password = _register(anonymous_client, "valid@example.test", "short")
    assert short_password.status_code == 400
    # Console delivery is explicitly recorded, not treated as SMTP delivery.
    assert _register(anonymous_client, "console@example.test").status_code == 201
    assert app.extensions["studyflow_mail_outbox"]
    assert "console@example.test" in app.extensions["studyflow_mail_outbox"][-1]["recipient"]
