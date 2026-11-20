"""Real-transaction rollback tests for active-token activation."""

from __future__ import annotations

import sqlite3
import threading

import pytest

import backend.accounts as accounts
from backend.db import connect_database, transaction
from backend.mailer import MailDeliveryError
from backend.utils.timeutils import now_iso

PASSWORD = "correct horse battery staple 2026"
EMAIL = "transaction@example.test"


def _register(client):
    return client.post(
        "/api/auth/register",
        json={"email": EMAIL, "password": PASSWORD, "display_name": "Transaction"},
    )


class FaultyConnection:
    """Real SQLite connection with fault injection after selected statements."""

    def __init__(self, conn, *, fail_after=None, fail_commit=False):
        self._conn = conn
        self._fail_after = fail_after
        self._fail_commit = fail_commit

    def execute(self, sql, params=()):
        cursor = self._conn.execute(sql, params)
        normalized = " ".join(sql.split())
        if self._fail_after == "active" and normalized.startswith(
            "UPDATE auth_accounts SET active_verification_token_id"
        ):
            raise RuntimeError("simulated failure after active update")
        if self._fail_after == "invalidate" and normalized.startswith(
            "UPDATE email_verification_tokens SET used_at"
        ):
            raise RuntimeError("simulated failure after old-token invalidation")
        return cursor

    def commit(self):
        if self._fail_commit:
            raise RuntimeError("simulated failure before commit")
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()


def test_discard_token_is_scoped_to_owning_account(app_factory):
    app = app_factory()
    client = app.test_client()
    assert _register(client).status_code == 201
    assert client.post(
        "/api/auth/register",
        json={
            "email": "other-owner@example.test",
            "password": PASSWORD,
            "display_name": "Other",
        },
    ).status_code == 201

    conn = sqlite3.connect(app.config["DATABASE_PATH"])
    conn.row_factory = sqlite3.Row
    try:
        first = conn.execute(
            "SELECT id FROM auth_accounts WHERE email = ?", (EMAIL,)
        ).fetchone()
        second = conn.execute(
            "SELECT id FROM auth_accounts WHERE email = ?",
            ("other-owner@example.test",),
        ).fetchone()
        second_token = conn.execute(
            "SELECT id FROM email_verification_tokens WHERE account_id = ? ORDER BY id",
            (second["id"],),
        ).fetchone()
        conn.execute(
            "UPDATE auth_accounts SET email_verified_at = ?, "
            "active_verification_token_id = NULL WHERE id = ?",
            (now_iso(), first["id"]),
        )
        conn.commit()
    finally:
        conn.close()

    # Use a deliberately mismatched account/token pair. The account_id guard
    # must prevent deletion of the other account's token.
    with app.app_context():
        accounts._discard_token_if_verified(first["id"], second_token["id"])

    conn = sqlite3.connect(app.config["DATABASE_PATH"])
    try:
        remaining = conn.execute(
            "SELECT id FROM email_verification_tokens WHERE id = ?",
            (second_token["id"],),
        ).fetchone()
    finally:
        conn.close()
    assert remaining is not None


def test_cleanup_and_another_activation_are_serialized(app_factory):
    app = app_factory()
    client = app.test_client()
    assert _register(client).status_code == 201
    started = threading.Event()
    release = threading.Event()
    errors = []
    original_send = accounts.send_verification_email

    with app.app_context():
        account_id = accounts.query_one(
            "SELECT id FROM auth_accounts WHERE lower(email) = ?", (EMAIL,)
        )["id"]
        with transaction() as db:
            _token, future_id = accounts._create_token(db, int(account_id))

    def fake_send(recipient, token):
        started.set()
        release.wait(5)
        raise MailDeliveryError("simulated SMTP failure")

    def failing_resend():
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
    thread = threading.Thread(target=failing_resend)
    try:
        thread.start()
        assert started.wait(5)
        # Activate B while A's SMTP failure is in flight; A's cleanup must not
        # remove B or clear B's active pointer.
        db = connect_database(app.config["DATABASE_PATH"])
        try:
            assert accounts._activate_token(db, int(account_id), int(future_id))
            db.commit()
        finally:
            db.close()
        release.set()
        thread.join(10)
    finally:
        accounts.send_verification_email = original_send

    assert len(errors) == 1
    conn = sqlite3.connect(app.config["DATABASE_PATH"])
    conn.row_factory = sqlite3.Row
    try:
        active = conn.execute(
            "SELECT active_verification_token_id FROM auth_accounts WHERE id = ?",
            (account_id,),
        ).fetchone()[0]
        future = conn.execute(
            "SELECT id, used_at FROM email_verification_tokens WHERE id = ?",
            (future_id,),
        ).fetchone()
    finally:
        conn.close()
    assert active == future_id
    assert future is not None
    assert future["used_at"] is None


def _state(database):
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    try:
        account = conn.execute(
            "SELECT id, active_verification_token_id FROM auth_accounts WHERE email = ?",
            (EMAIL,),
        ).fetchone()
        tokens = conn.execute(
            "SELECT id, used_at FROM email_verification_tokens "
            "WHERE account_id = ? ORDER BY id",
            (account["id"],),
        ).fetchall()
    finally:
        conn.close()
    return account, tokens


@pytest.mark.parametrize("failure", ["active", "invalidate", "commit"])
def test_activation_transaction_rolls_back_all_stages(app_factory, failure):
    app = app_factory()
    client = app.test_client()
    assert _register(client).status_code == 201

    with app.app_context():
        account_id = accounts.query_one(
            "SELECT id FROM auth_accounts WHERE lower(email) = ?", (EMAIL,)
        )["id"]
        initial_active = accounts.query_one(
            "SELECT active_verification_token_id FROM auth_accounts WHERE id = ?",
            (account_id,),
        )["active_verification_token_id"]
        with transaction() as db:
            _token, new_token_id = accounts._create_token(db, int(account_id))

    raw = connect_database(app.config["DATABASE_PATH"])
    proxy = FaultyConnection(
        raw,
        fail_after=None if failure == "commit" else failure,
        fail_commit=failure == "commit",
    )
    try:
        with pytest.raises(RuntimeError, match="simulated"):
            try:
                accounts._activate_token(proxy, int(account_id), int(new_token_id))
                proxy.commit()
            except RuntimeError:
                proxy.rollback()
                raise
    finally:
        raw.close()

    account, tokens = _state(app.config["DATABASE_PATH"])
    assert account["active_verification_token_id"] == initial_active
    # The new token must not have become active, and the old active token
    # must still be unused.
    by_id = {row["id"]: row["used_at"] for row in tokens}
    assert by_id[new_token_id] is None
    assert by_id[initial_active] is None
