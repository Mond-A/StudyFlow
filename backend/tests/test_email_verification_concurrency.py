"""Concurrency regressions for per-account verification-token replacement."""

from __future__ import annotations

import hashlib
import sqlite3
import threading
from datetime import datetime

import backend.accounts as accounts
from backend.mailer import MailDeliveryError

PASSWORD = "correct horse battery staple 2026"
EMAIL = "concurrent@example.test"


def _register(client):
    return client.post(
        "/api/auth/register",
        json={"email": EMAIL, "password": PASSWORD, "display_name": "Concurrent"},
    )


def _initial_token(app):
    outbox = app.extensions.get("studyflow_mail_outbox", [])
    assert outbox
    url = outbox[-1]["verification_url"]
    return url.split("token=", 1)[1]


def _token_id(conn, token):
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    row = conn.execute(
        "SELECT id FROM email_verification_tokens WHERE token_hash = ?", (digest,)
    ).fetchone()
    assert row is not None
    return int(row[0])


def _db_state(app):
    conn = sqlite3.connect(app.config["DATABASE_PATH"])
    try:
        account = conn.execute(
            "SELECT id, active_verification_token_id FROM auth_accounts WHERE email = ?",
            (EMAIL,),
        ).fetchone()
        rows = conn.execute(
            "SELECT id, used_at FROM email_verification_tokens "
            "WHERE account_id = ? ORDER BY id",
            (account[0],),
        ).fetchall()
    finally:
        conn.close()
    return account, rows


def _run_concurrent(
    app,
    *,
    count=2,
    fail_smtp=False,
    fail_activation=False,
    late_first=False,
):
    barrier = threading.Barrier(count)
    late_first_done = threading.Event()
    sent = []
    calls = []
    errors = []
    lock = threading.Lock()
    original_send = accounts.send_verification_email
    original_activate = accounts._activate_token

    def fake_send(recipient, token):
        with lock:
            index = len(calls)
            calls.append(token)
        barrier.wait(timeout=10)
        if late_first and index == 0:
            late_first_done.wait(timeout=10)
        if fail_smtp and index == 0:
            raise MailDeliveryError("simulated SMTP failure")
        with lock:
            sent.append(token)

    def fake_activate(db, account_id, token_id):
        if fail_activation and threading.current_thread().name == "db-fail":
            raise sqlite3.OperationalError("simulated database failure")
        result = original_activate(db, account_id, token_id)
        if late_first and threading.current_thread().name == "worker-1":
            late_first_done.set()
        return result

    accounts.send_verification_email = fake_send
    if fail_activation or late_first:
        accounts._activate_token = fake_activate

    def worker(name):
        try:
            with app.test_request_context(
                "/api/auth/resend-verification",
                method="POST",
                environ_base={"REMOTE_ADDR": "127.0.0.1"},
            ):
                accounts.resend_verification(EMAIL)
        except Exception as exc:  # noqa: BLE001 - test records failures
            with lock:
                errors.append((name, type(exc).__name__, str(exc)))

    threads = [
        threading.Thread(
            target=worker,
            args=("db-fail" if fail_activation and i == 0 else f"worker-{i}",),
            name="db-fail" if fail_activation and i == 0 else f"worker-{i}",
        )
        for i in range(count)
    ]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(15)
    finally:
        accounts.send_verification_email = original_send
        accounts._activate_token = original_activate
    assert not any(thread.is_alive() for thread in threads)
    return sent, errors


def _app(app_factory):
    return app_factory(
        REGISTER_IP_LIMIT=100,
        REGISTER_EMAIL_LIMIT=100,
        REGISTER_GLOBAL_LIMIT=100,
        RESEND_IP_LIMIT=100,
        RESEND_EMAIL_LIMIT=100,
        RESEND_GLOBAL_LIMIT=100,
        ACCOUNT_RATE_WINDOW_SECONDS=3600,
    )


def _assert_one_valid(app, initial_token, sent):
    account, rows = _db_state(app)
    active = account[1]
    unused = [row for row in rows if row[1] is None]
    assert active is not None
    assert [row[0] for row in unused] == [active]

    conn = sqlite3.connect(app.config["DATABASE_PATH"])
    try:
        initial_id = _token_id(conn, initial_token)
        sent_ids = [_token_id(conn, token) for token in sent]
    finally:
        conn.close()

    client = app.test_client()
    for token, token_id in zip([initial_token, *sent], [initial_id, *sent_ids]):
        location = client.get(f"/verify-email?token={token}").headers["Location"]
        if token_id == active:
            assert location.endswith("verified=1")
        else:
            assert location.endswith("verified=0")


def test_two_successful_concurrent_resends_leave_one_valid_token(app_factory):
    app = _app(app_factory)
    client = app.test_client()
    assert _register(client).status_code == 201
    initial = _initial_token(app)

    sent, errors = _run_concurrent(app)
    assert errors == []
    assert len(sent) == 2
    _assert_one_valid(app, initial, sent)


def test_early_request_finishing_late_does_not_override_newer_active(app_factory):
    app = _app(app_factory)
    client = app.test_client()
    assert _register(client).status_code == 201
    initial = _initial_token(app)

    sent, errors = _run_concurrent(app, late_first=True)
    assert errors == []
    assert len(sent) == 2
    _assert_one_valid(app, initial, sent)


def test_concurrent_resend_with_one_smtp_failure_keeps_one_valid_token(app_factory):
    app = _app(app_factory)
    client = app.test_client()
    assert _register(client).status_code == 201
    initial = _initial_token(app)

    sent, errors = _run_concurrent(app, fail_smtp=True)
    assert len(errors) == 1
    assert len(sent) == 1
    _assert_one_valid(app, initial, sent)


def test_concurrent_resend_with_database_activation_failure_never_zeroes_tokens(app_factory):
    app = _app(app_factory)
    client = app.test_client()
    assert _register(client).status_code == 201
    initial = _initial_token(app)

    sent, errors = _run_concurrent(app, fail_activation=True)
    assert len(errors) == 1
    assert len(sent) == 2

    account, rows = _db_state(app)
    assert account[1] is not None
    active_rows = [row for row in rows if row[0] == account[1]]
    assert len(active_rows) == 1
    assert active_rows[0][1] is None
    assert any(row[1] is None for row in rows)
    # The failed activation may leave the other successfully-sent token
    # unused, but the active token must remain usable.
    assert initial


def _assert_invariants(app):
    conn = sqlite3.connect(app.config["DATABASE_PATH"])
    conn.row_factory = sqlite3.Row
    try:
        account = conn.execute(
            "SELECT id, email_verified_at, active_verification_token_id "
            "FROM auth_accounts WHERE email = ?",
            (EMAIL,),
        ).fetchone()
        if account["email_verified_at"] is not None:
            assert account["active_verification_token_id"] is None
        if account["active_verification_token_id"] is not None:
            token = conn.execute(
                "SELECT account_id, used_at, expires_at "
                "FROM email_verification_tokens WHERE id = ?",
                (account["active_verification_token_id"],),
            ).fetchone()
            assert token is not None
            assert token["account_id"] == account["id"]
            assert token["used_at"] is None
            assert datetime.fromisoformat(token["expires_at"]) > datetime.now().astimezone()
    finally:
        conn.close()


def test_verified_account_resend_does_not_send_or_reactivate(app_factory):
    app = _app(app_factory)
    client = app.test_client()
    assert _register(client).status_code == 201
    initial = _initial_token(app)
    with app.app_context():
        accounts.verify_email_token(initial)
    before = len(app.extensions.get("studyflow_mail_outbox", []))

    response = client.post(
        "/api/auth/resend-verification", json={"email": EMAIL}
    )
    assert response.status_code == 200
    assert len(app.extensions.get("studyflow_mail_outbox", [])) == before
    _assert_invariants(app)


def test_verification_before_send_prevents_email_and_active(app_factory):
    app = _app(app_factory)
    client = app.test_client()
    assert _register(client).status_code == 201
    initial = _initial_token(app)
    sent = []
    original_discard = accounts._discard_token_if_verified
    original_send = accounts.send_verification_email

    def verify_then_discard(account_id, token_id):
        with app.app_context():
            accounts.verify_email_token(initial)
        return original_discard(account_id, token_id)

    def fake_send(recipient, token):
        sent.append(token)

    accounts._discard_token_if_verified = verify_then_discard
    accounts.send_verification_email = fake_send
    try:
        with app.test_request_context(
            "/api/auth/resend-verification",
            method="POST",
            environ_base={"REMOTE_ADDR": "127.0.0.1"},
        ):
            accounts.resend_verification(EMAIL)
    finally:
        accounts._discard_token_if_verified = original_discard
        accounts.send_verification_email = original_send

    assert sent == []
    _assert_invariants(app)


def test_verification_during_send_clears_active_after_activation(app_factory):
    app = _app(app_factory)
    client = app.test_client()
    assert _register(client).status_code == 201
    initial = _initial_token(app)
    started = threading.Event()
    release = threading.Event()
    sent = []
    errors = []
    original_send = accounts.send_verification_email

    def fake_send(recipient, token):
        sent.append(token)
        started.set()
        release.wait(5)

    def worker():
        try:
            with app.test_request_context(
                "/api/auth/resend-verification",
                method="POST",
                environ_base={"REMOTE_ADDR": "127.0.0.1"},
            ):
                accounts.resend_verification(EMAIL)
        except Exception as exc:  # noqa: BLE001
            errors.append(repr(exc))

    accounts.send_verification_email = fake_send
    thread = threading.Thread(target=worker)
    try:
        thread.start()
        assert started.wait(5)
        with app.app_context():
            accounts.verify_email_token(initial)
        release.set()
        thread.join(10)
    finally:
        accounts.send_verification_email = original_send
    assert errors == []
    assert len(sent) == 1
    _assert_invariants(app)


def test_verification_after_smtp_before_activation_clears_active(app_factory):
    app = _app(app_factory)
    client = app.test_client()
    assert _register(client).status_code == 201
    initial = _initial_token(app)
    before_activation = threading.Event()
    release = threading.Event()
    sent = []
    errors = []
    original_send = accounts.send_verification_email
    original_activate = accounts._activate_token

    def fake_send(recipient, token):
        sent.append(token)

    def paused_activate(db, account_id, token_id):
        before_activation.set()
        release.wait(5)
        return original_activate(db, account_id, token_id)

    def worker():
        try:
            with app.test_request_context(
                "/api/auth/resend-verification",
                method="POST",
                environ_base={"REMOTE_ADDR": "127.0.0.1"},
            ):
                accounts.resend_verification(EMAIL)
        except Exception as exc:  # noqa: BLE001
            errors.append(repr(exc))

    accounts.send_verification_email = fake_send
    accounts._activate_token = paused_activate
    thread = threading.Thread(target=worker)
    try:
        thread.start()
        assert before_activation.wait(5)
        with app.app_context():
            accounts.verify_email_token(initial)
        release.set()
        thread.join(10)
    finally:
        accounts.send_verification_email = original_send
        accounts._activate_token = original_activate

    assert errors == []
    assert len(sent) == 1
    _assert_invariants(app)
    conn = sqlite3.connect(app.config["DATABASE_PATH"])
    try:
        account = conn.execute(
            "SELECT email_verified_at, active_verification_token_id "
            "FROM auth_accounts WHERE email = ?",
            (EMAIL,),
        ).fetchone()
    finally:
        conn.close()
    assert account[0] is not None
    assert account[1] is None


def test_concurrent_verification_and_resend_leave_consistent_state(app_factory):
    app = _app(app_factory)
    client = app.test_client()
    assert _register(client).status_code == 201
    initial = _initial_token(app)

    barrier = threading.Barrier(2)
    errors = []
    original_send = accounts.send_verification_email

    def fake_send(recipient, token):
        return None

    def verify_worker():
        try:
            barrier.wait(timeout=5)
            local_client = app.test_client()
            response = local_client.get(f"/verify-email?token={initial}")
            assert response.status_code == 302
        except Exception as exc:  # noqa: BLE001
            errors.append(repr(exc))

    def resend_worker():
        try:
            barrier.wait(timeout=5)
            with app.test_request_context(
                "/api/auth/resend-verification",
                method="POST",
                environ_base={"REMOTE_ADDR": "127.0.0.1"},
            ):
                accounts.resend_verification(EMAIL)
        except Exception as exc:  # noqa: BLE001
            errors.append(repr(exc))

    accounts.send_verification_email = fake_send
    try:
        threads = [
            threading.Thread(target=verify_worker),
            threading.Thread(target=resend_worker),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)
    finally:
        accounts.send_verification_email = original_send

    assert errors == []
    conn = sqlite3.connect(app.config["DATABASE_PATH"])
    conn.row_factory = sqlite3.Row
    try:
        account = conn.execute(
            "SELECT email_verified_at, active_verification_token_id "
            "FROM auth_accounts WHERE email = ?",
            (EMAIL,),
        ).fetchone()
        if account["email_verified_at"] is None:
            assert account["active_verification_token_id"] is not None
            active = conn.execute(
                "SELECT used_at, expires_at FROM email_verification_tokens WHERE id = ?",
                (account["active_verification_token_id"],),
            ).fetchone()
            assert active["used_at"] is None
    finally:
        conn.close()
    _assert_invariants(app)


def test_repeated_concurrent_resends_keep_exactly_one_valid_token(app_factory):
    app = _app(app_factory)
    client = app.test_client()
    assert _register(client).status_code == 201
    initial = _initial_token(app)

    for _ in range(3):
        sent, errors = _run_concurrent(app, count=2)
        assert errors == []
        assert len(sent) == 2
        account, rows = _db_state(app)
        active = account[1]
        unused = [row for row in rows if row[1] is None]
        assert active is not None
        assert [row[0] for row in unused] == [active]
    assert initial
