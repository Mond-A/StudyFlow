"""Regression tests for v1.1.1 email-verification hardening."""

from __future__ import annotations

import logging
import socket
import sqlite3
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from flask import Flask

import backend.accounts as accounts
import backend.auth as auth
import backend.mailer as mailer
import backend.rate_limit as rate_limit
from backend.db import connect_database, init_schema
from backend.mailer import MailDeliveryError
from backend.rate_limit import RateLimitUnavailable

PASSWORD = "correct horse battery staple 2026"


def _latest_token(app) -> str:
    outbox = app.extensions.get("studyflow_mail_outbox", [])
    assert outbox, "console backend should record a verification message"
    url = outbox[-1]["verification_url"]
    return parse_qs(urlsplit(url).query)["token"][0]


def _register(client, email: str, *, remote_addr: str | None = None):
    kwargs = {}
    if remote_addr:
        kwargs["environ_base"] = {"REMOTE_ADDR": remote_addr}
    return client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "display_name": email.split("@")[0],
        },
        **kwargs,
    )


def _high_registration_limits(**overrides):
    values = {
        "REGISTER_IP_LIMIT": 100,
        "REGISTER_EMAIL_LIMIT": 100,
        "REGISTER_GLOBAL_LIMIT": 100,
        "RESEND_IP_LIMIT": 100,
        "RESEND_EMAIL_LIMIT": 100,
        "RESEND_GLOBAL_LIMIT": 100,
        "ACCOUNT_RATE_WINDOW_SECONDS": 3600,
    }
    values.update(overrides)
    return values


def test_registration_ip_limit_is_isolated_by_ip(app_factory):
    app = app_factory(**_high_registration_limits(REGISTER_IP_LIMIT=2))
    client = app.test_client()

    assert _register(client, "one@example.test").status_code == 201
    assert _register(client, "two@example.test").status_code == 201
    blocked = _register(client, "three@example.test")
    assert blocked.status_code == 429
    assert blocked.get_json()["error"]["code"] == "RATE_LIMITED"
    assert int(blocked.headers["Retry-After"]) >= 1

    other_ip = _register(client, "four@example.test", remote_addr="198.51.100.22")
    assert other_ip.status_code == 201


def test_registration_email_limit_is_isolated_by_email(app_factory):
    app = app_factory(**_high_registration_limits(REGISTER_EMAIL_LIMIT=1))
    client = app.test_client()

    assert _register(client, "same@example.test").status_code == 201
    blocked = _register(client, "same@example.test")
    assert blocked.status_code == 429
    assert blocked.get_json()["error"]["code"] == "RATE_LIMITED"
    assert _register(client, "other@example.test").status_code == 201


def test_registration_global_limit(app_factory):
    app = app_factory(**_high_registration_limits(REGISTER_GLOBAL_LIMIT=1))
    client = app.test_client()

    assert _register(client, "first@example.test").status_code == 201
    blocked = _register(client, "second@example.test", remote_addr="198.51.100.23")
    assert blocked.status_code == 429
    assert blocked.get_json()["error"]["code"] == "RATE_LIMITED"


def test_resend_ip_limit_is_isolated_by_ip(app_factory):
    app = app_factory(
        **_high_registration_limits(
            RESEND_IP_LIMIT=2,
            RESEND_EMAIL_LIMIT=100,
        )
    )
    client = app.test_client()
    assert _register(client, "resend@example.test").status_code == 201

    assert client.post(
        "/api/auth/resend-verification", json={"email": "resend@example.test"}
    ).status_code == 200
    assert client.post(
        "/api/auth/resend-verification", json={"email": "resend@example.test"}
    ).status_code == 200
    blocked = client.post(
        "/api/auth/resend-verification", json={"email": "resend@example.test"}
    )
    assert blocked.status_code == 429
    assert blocked.get_json()["error"]["code"] == "RATE_LIMITED"

    other_ip = client.post(
        "/api/auth/resend-verification",
        json={"email": "resend@example.test"},
        environ_base={"REMOTE_ADDR": "198.51.100.24"},
    )
    assert other_ip.status_code == 200


def test_resend_email_limit_is_isolated_by_email(app_factory):
    app = app_factory(
        **_high_registration_limits(
            RESEND_IP_LIMIT=100,
            RESEND_EMAIL_LIMIT=1,
        )
    )
    client = app.test_client()
    assert _register(client, "resend-a@example.test").status_code == 201
    assert _register(client, "resend-b@example.test").status_code == 201

    assert client.post(
        "/api/auth/resend-verification", json={"email": "resend-a@example.test"}
    ).status_code == 200
    blocked = client.post(
        "/api/auth/resend-verification", json={"email": "resend-a@example.test"}
    )
    assert blocked.status_code == 429
    assert blocked.get_json()["error"]["code"] == "RATE_LIMITED"

    assert client.post(
        "/api/auth/resend-verification", json={"email": "resend-b@example.test"}
    ).status_code == 200


def test_resend_global_limit(app_factory):
    app = app_factory(
        **_high_registration_limits(
            RESEND_IP_LIMIT=100,
            RESEND_EMAIL_LIMIT=100,
            RESEND_GLOBAL_LIMIT=1,
        )
    )
    client = app.test_client()
    assert _register(client, "global-a@example.test").status_code == 201
    assert _register(client, "global-b@example.test").status_code == 201

    assert client.post(
        "/api/auth/resend-verification", json={"email": "global-a@example.test"}
    ).status_code == 200
    blocked = client.post(
        "/api/auth/resend-verification", json={"email": "global-b@example.test"}
    )
    assert blocked.status_code == 429
    assert blocked.get_json()["error"]["code"] == "RATE_LIMITED"


def test_registration_smtp_failure_keeps_account_unverified(app_factory, monkeypatch):
    app = app_factory(**_high_registration_limits())
    client = app.test_client()

    def fail(*args, **kwargs):
        raise MailDeliveryError("simulated SMTP failure")

    monkeypatch.setattr(accounts, "send_verification_email", fail)
    response = _register(client, "smtp-fail@example.test")
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "EMAIL_DELIVERY_FAILED"

    conn = sqlite3.connect(app.config["DATABASE_PATH"])
    try:
        verified = conn.execute(
            "SELECT email_verified_at FROM auth_accounts WHERE email = ?",
            ("smtp-fail@example.test",),
        ).fetchone()[0]
    finally:
        conn.close()
    assert verified is None


def test_resend_smtp_failure_preserves_old_token(app_factory, monkeypatch):
    app = app_factory(**_high_registration_limits())
    client = app.test_client()
    assert _register(client, "keep-old-token@example.test").status_code == 201
    old_token = _latest_token(app)

    def fail(*args, **kwargs):
        raise MailDeliveryError("simulated SMTP failure")

    monkeypatch.setattr(accounts, "send_verification_email", fail)
    response = client.post(
        "/api/auth/resend-verification",
        json={"email": "keep-old-token@example.test"},
    )
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "EMAIL_DELIVERY_FAILED"

    verified = client.get(f"/verify-email?token={old_token}")
    assert verified.status_code == 302
    assert verified.headers["Location"].endswith("/login?verified=1")


def test_resend_success_invalidates_old_token(app_factory):
    app = app_factory(**_high_registration_limits())
    client = app.test_client()
    assert _register(client, "replace-token@example.test").status_code == 201
    old_token = _latest_token(app)

    assert client.post(
        "/api/auth/resend-verification", json={"email": "replace-token@example.test"}
    ).status_code == 200
    new_token = _latest_token(app)
    assert new_token != old_token

    old = client.get(f"/verify-email?token={old_token}")
    assert old.headers["Location"].endswith("/login?verified=0")
    new = client.get(f"/verify-email?token={new_token}")
    assert new.headers["Location"].endswith("/login?verified=1")


def test_api_verification_and_invalid_token(app_factory):
    app = app_factory(**_high_registration_limits())
    client = app.test_client()
    assert _register(client, "api-verify@example.test").status_code == 201
    token = _latest_token(app)

    invalid = client.post("/api/auth/verify-email", json={"token": "not-a-real-token"})
    assert invalid.status_code == 400
    assert invalid.get_json()["error"]["code"] == "INVALID_VERIFICATION_TOKEN"

    verified = client.post("/api/auth/verify-email", json={"token": token})
    assert verified.status_code == 200
    assert verified.get_json()["data"]["verified"] is True
    assert client.post(
        "/api/auth/login",
        json={"email": "api-verify@example.test", "password": PASSWORD},
    ).status_code == 200


def test_console_logs_do_not_include_token(app_factory, caplog):
    app = app_factory()
    token = "sensitive-token-value"
    with app.app_context():
        with caplog.at_level(logging.WARNING):
            mailer.send_verification_email("log@example.test", token)
    assert token not in caplog.text
    assert "verify-email?token=" not in caplog.text


def test_access_log_format_excludes_query_string():
    config = Path("deploy/gunicorn.conf.py").read_text(encoding="utf-8")
    assert "%(m)s %(U)s %(H)s" in config
    assert "%(r)s" not in config
    assert "%(q)s" not in config


def _public_dns(*args, **kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]


def test_production_console_mail_backend_fails_closed(app_factory, monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setattr(auth.socket, "getaddrinfo", _public_dns)
    app = app_factory(
        TESTING=False,
        MAIL_BACKEND="console",
        PUBLIC_BASE_URL="https://studyflow.example.test",
    )
    with app.app_context():
        with pytest.raises(MailDeliveryError, match="disabled in production"):
            mailer.send_verification_email("prod@example.test", "token")
        assert "studyflow_mail_outbox" not in app.extensions


def test_production_rejects_insecure_public_base_url(app_factory, monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "production")
    with pytest.raises(RuntimeError, match="PUBLIC_BASE_URL"):
        app_factory(
            TESTING=False,
            PUBLIC_BASE_URL="http://127.0.0.1:5000",
        )


@pytest.mark.parametrize(
    "base_url",
    [
        "https://localhost:5000",
        "https://127.0.0.1:5000",
        "https://example.com:99999",
        "https://user:pass@example.com",
        "https://example.com?token=leak",
        "https://example.com#fragment",
        "https://example.com:0",
    ],
)
def test_production_rejects_invalid_public_base_urls(app_factory, monkeypatch, base_url):
    monkeypatch.setenv("FLASK_ENV", "production")
    with pytest.raises(RuntimeError, match="PUBLIC_BASE_URL"):
        app_factory(TESTING=False, PUBLIC_BASE_URL=base_url)


def test_development_allows_local_http_public_base_url(app_factory):
    app = app_factory(PUBLIC_BASE_URL="http://127.0.0.1:5000")
    assert app.config["PUBLIC_BASE_URL"] == "http://127.0.0.1:5000"


def test_production_accepts_external_https_public_base_url(app_factory, monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setattr(auth.socket, "getaddrinfo", _public_dns)
    app = app_factory(
        TESTING=False,
        PUBLIC_BASE_URL="https://studyflow.example.test",
    )
    assert app.config["PUBLIC_BASE_URL"] == "https://studyflow.example.test"


def test_production_rejects_hostname_resolving_to_private_address(app_factory, monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setattr(
        auth.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
        ],
    )
    with pytest.raises(RuntimeError, match="non-public"):
        app_factory(TESTING=False, PUBLIC_BASE_URL="https://127.1")


def test_production_rejects_mixed_public_and_private_dns_answers(app_factory, monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setattr(
        auth.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443)),
        ],
    )
    with pytest.raises(RuntimeError, match="non-public"):
        app_factory(TESTING=False, PUBLIC_BASE_URL="https://studyflow.example.test")


def test_production_rejects_dns_failure(app_factory, monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "production")

    def fail(*args, **kwargs):
        raise socket.gaierror("temporary failure")

    monkeypatch.setattr(auth.socket, "getaddrinfo", fail)
    with pytest.raises(RuntimeError, match="could not be resolved"):
        app_factory(TESTING=False, PUBLIC_BASE_URL="https://studyflow.example.test")


def test_production_allows_localhost_string_with_public_dns(app_factory, monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setattr(auth.socket, "getaddrinfo", _public_dns)
    app = app_factory(
        TESTING=False,
        PUBLIC_BASE_URL="https://localhost.example.com",
    )
    assert app.config["PUBLIC_BASE_URL"] == "https://localhost.example.com"


def test_v110_auth_accounts_gains_active_token_column_idempotently(tmp_path):
    database = tmp_path / "v110.sqlite"
    conn = connect_database(database)
    try:
        conn.execute(
            """
            CREATE TABLE auth_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                email_verified_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()

    app = Flask(__name__)
    app.config.update(DATABASE_PATH=str(database), TIMEZONE="Asia/Shanghai")
    with app.app_context():
        init_schema(app)
        init_schema(app)

    conn = connect_database(database)
    try:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(auth_accounts)").fetchall()
        }
    finally:
        conn.close()
    assert "active_verification_token_id" in columns


def test_rate_limit_operational_error_is_unavailable_and_rolls_back(monkeypatch):
    class BusyConnection:
        rolled_back = False

        def execute(self, *args, **kwargs):
            raise sqlite3.OperationalError("database is locked")

        def rollback(self):
            self.rolled_back = True

    busy = BusyConnection()
    monkeypatch.setattr(rate_limit, "get_db", lambda: busy)
    with pytest.raises(RateLimitUnavailable):
        rate_limit.consume_limits([("test:busy", 1, 3600)])
    assert busy.rolled_back is True


def test_rate_limit_connection_failure_is_unavailable(monkeypatch):
    def fail():
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(rate_limit, "get_db", fail)
    with pytest.raises(RateLimitUnavailable):
        rate_limit.consume_limits([("test:connection", 1, 3600)])


def test_registration_rate_limit_unavailable_returns_503(app_factory, monkeypatch):
    app = app_factory()
    client = app.test_client()

    def unavailable(*args, **kwargs):
        raise RateLimitUnavailable("database is locked")

    monkeypatch.setattr(accounts, "consume_limits", unavailable)
    response = _register(client, "busy-limit@example.test")
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "RATE_LIMIT_UNAVAILABLE"


def test_smtp_backend_never_uses_console_outbox(app_factory, monkeypatch):
    app = app_factory(
        MAIL_BACKEND="smtp",
        SMTP_HOST="smtp.example.test",
        SMTP_PORT=587,
        SMTP_USE_TLS=False,
        SMTP_USE_SSL=False,
    )

    class FakeSMTP:
        sent = []

        def __init__(self, host, port, timeout):
            self.host = host
            self.port = port
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def starttls(self, context=None):
            return None

        def login(self, username, password):
            return None

        def send_message(self, message):
            self.sent.append(message)

    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)
    with app.app_context():
        mailer.send_verification_email("smtp@example.test", "token")
        assert "studyflow_mail_outbox" not in app.extensions


def test_login_ui_exposes_resend_for_failure_paths():
    source = Path("frontend/js/login.js").read_text(encoding="utf-8")
    verified_failure = source.index('params.get("verified") === "0"')
    assert "revealResend()" in source[verified_failure : verified_failure + 250]

    unverified = source.index('params.get("error") === "unverified"')
    assert "revealResend()" in source[unverified : unverified + 250]

    delivery_failure = source.index('payload.error.code === "EMAIL_DELIVERY_FAILED"')
    assert "revealResend()" in source[delivery_failure : delivery_failure + 350]
