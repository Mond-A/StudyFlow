"""Email account registration, verification, and authentication primitives."""

from __future__ import annotations

import hashlib
import re
import secrets
import sqlite3
from datetime import datetime, timedelta

from flask import current_app, request
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db, query_one, transaction
from .mailer import MailDeliveryError, send_verification_email
from .rate_limit import RateLimitUnavailable, consume_limits
from .utils.exceptions import APIError
from .utils.timeutils import now_iso

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_INVALID_LOGIN = "邮箱或密码错误"


def normalize_email(value: object) -> str:
    email = str(value or "").strip().lower()
    if len(email) > 254 or not _EMAIL_RE.fullmatch(email):
        raise APIError("请输入有效的邮箱地址", code="VALIDATION_ERROR", status_code=400)
    return email


def validate_password(value: object) -> str:
    password = str(value or "")
    minimum = int(current_app.config["PASSWORD_MIN_LENGTH"])
    if len(password) < minimum:
        raise APIError(
            f"密码至少需要 {minimum} 个字符",
            code="WEAK_PASSWORD",
            status_code=400,
        )
    if len(password) > 256:
        raise APIError("密码过长", code="VALIDATION_ERROR", status_code=400)
    return password


def _display_name(value: object, email: str) -> str:
    name = str(value or "").strip() or email.split("@", 1)[0]
    if len(name) > 80:
        raise APIError("显示名称过长", code="VALIDATION_ERROR", status_code=400)
    return name


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _create_token(db, account_id: int) -> tuple[str, int]:
    """Create a token without invalidating other still-valid tokens."""
    token = secrets.token_urlsafe(32)
    expires_at = (
        datetime.now().astimezone()
        + timedelta(hours=int(current_app.config["EMAIL_VERIFICATION_HOURS"]))
    ).isoformat(timespec="seconds")
    cursor = db.execute(
        """
        INSERT INTO email_verification_tokens
            (account_id, token_hash, expires_at, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (account_id, _token_hash(token), expires_at, now_iso()),
    )
    return token, int(cursor.lastrowid)


def _activate_token(db, account_id: int, token_id: int) -> bool:
    """Select the newest successfully delivered token as the active link.

    The email_verified_at state is re-read inside BEGIN IMMEDIATE. If a
    concurrent verification completed after resend started, this method must
    not reactivate the account or its token. Token ids are monotonic and are
    used as the ordering token.
    """
    db.execute("BEGIN IMMEDIATE")
    row = db.execute(
        "SELECT active_verification_token_id, email_verified_at "
        "FROM auth_accounts WHERE id = ?",
        (account_id,),
    ).fetchone()
    if row is None:
        return False
    if row["email_verified_at"]:
        db.execute(
            "UPDATE auth_accounts SET active_verification_token_id = NULL "
            "WHERE id = ?",
            (account_id,),
        )
        db.execute(
            "UPDATE email_verification_tokens SET used_at = ? "
            "WHERE id = ? AND used_at IS NULL",
            (now_iso(), token_id),
        )
        return False

    current = int(row["active_verification_token_id"] or 0)
    active = max(current, token_id)
    if active != current:
        db.execute(
            """
            UPDATE auth_accounts
            SET active_verification_token_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (active, now_iso(), account_id),
        )
    db.execute(
        """
        UPDATE email_verification_tokens
        SET used_at = ?
        WHERE account_id = ? AND used_at IS NULL AND id < ?
        """,
        (now_iso(), account_id, active),
    )
    return True


def _discard_token_if_verified(account_id: int, token_id: int) -> bool:
    """Short pre-SMTP transaction: do not send for an already-verified account."""
    with transaction() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT email_verified_at FROM auth_accounts WHERE id = ?",
            (account_id,),
        ).fetchone()
        if row is None:
            db.execute(
                "DELETE FROM email_verification_tokens "
                "WHERE id = ? AND account_id = ?",
                (token_id, account_id),
            )
            return True
        if row["email_verified_at"]:
            db.execute(
                "UPDATE auth_accounts SET active_verification_token_id = NULL "
                "WHERE id = ?",
                (account_id,),
            )
            db.execute(
                "DELETE FROM email_verification_tokens "
                "WHERE id = ? AND account_id = ?",
                (token_id, account_id),
            )
            return True
    return False


def _consume_account_action_limits(action: str, email: str) -> None:
    prefix = action.upper()
    window = int(current_app.config["ACCOUNT_RATE_WINDOW_SECONDS"])
    limits = [
        (
            f"{action}:global",
            int(current_app.config[f"{prefix}_GLOBAL_LIMIT"]),
            window,
        ),
        (
            f"{action}:ip:{request.remote_addr or 'unknown'}",
            int(current_app.config[f"{prefix}_IP_LIMIT"]),
            window,
        ),
        (
            f"{action}:email:{email}",
            int(current_app.config[f"{prefix}_EMAIL_LIMIT"]),
            window,
        ),
    ]
    try:
        retry_after = consume_limits(limits)
    except RateLimitUnavailable as exc:
        raise APIError(
            "限流服务暂时不可用，请稍后再试",
            code="RATE_LIMIT_UNAVAILABLE",
            status_code=503,
        ) from exc
    if retry_after:
        raise APIError(
            "请求过于频繁，请稍后再试",
            code="RATE_LIMITED",
            status_code=429,
            details={"retry_after": retry_after},
        )


def register_account(email_value: object, password_value: object, display_value: object = "") -> dict:
    email = normalize_email(email_value)
    password = validate_password(password_value)
    display_name = _display_name(display_value, email)
    _consume_account_action_limits("register", email)
    existing = query_one("SELECT id FROM auth_accounts WHERE lower(email) = ?", (email,))
    if existing is not None:
        raise APIError("该邮箱已注册", code="EMAIL_ALREADY_REGISTERED", status_code=409)
    timestamp = now_iso()
    try:
        with transaction() as db:
            cursor = db.execute(
                """
                INSERT INTO users
                    (username, display_name, email, avatar_color, daily_goal_minutes,
                     pomodoro_minutes, short_break_minutes, long_break_minutes,
                     timezone, created_at, updated_at)
                VALUES (?, ?, ?, ?, 120, 25, 5, 15, ?, ?, ?)
                """,
                (
                    email,
                    display_name,
                    email,
                    "#2563eb",
                    current_app.config.get("TIMEZONE", "Asia/Shanghai"),
                    timestamp,
                    timestamp,
                ),
            )
            user_id = int(cursor.lastrowid)
            account_cursor = db.execute(
                """
                INSERT INTO auth_accounts
                    (user_id, email, password_hash, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    email,
                    generate_password_hash(password, method="scrypt"),
                    timestamp,
                    timestamp,
                ),
            )
            account_id = int(account_cursor.lastrowid)
            token, token_id = _create_token(db, account_id)
            db.execute(
                "UPDATE auth_accounts SET active_verification_token_id = ? WHERE id = ?",
                (token_id, account_id),
            )
    except sqlite3.IntegrityError as exc:
        raise APIError("该邮箱已注册", code="EMAIL_ALREADY_REGISTERED", status_code=409) from exc

    try:
        send_verification_email(email, token)
    except MailDeliveryError as exc:
        # The account remains unverified and can resend after SMTP is fixed.
        raise APIError(
            "账户已创建，但验证邮件暂时无法发送，请稍后重新发送验证邮件",
            code="EMAIL_DELIVERY_FAILED",
            status_code=503,
        ) from exc
    return {"email": email, "verification_required": True}


def verify_email_token(token_value: object) -> dict:
    token = str(token_value or "").strip()
    if not token or len(token) > 200:
        raise APIError("验证链接无效或已过期", code="INVALID_VERIFICATION_TOKEN", status_code=400)
    token_hash = _token_hash(token)
    row = query_one(
        """
        SELECT t.id, t.account_id, t.expires_at, t.used_at,
               a.email, a.email_verified_at, a.active_verification_token_id
        FROM email_verification_tokens t
        JOIN auth_accounts a ON a.id = t.account_id
        WHERE t.token_hash = ?
        """,
        (token_hash,),
    )
    if (
        row is None
        or row["used_at"]
        or row["email_verified_at"]
        or row["active_verification_token_id"] != row["id"]
    ):
        raise APIError("验证链接无效或已过期", code="INVALID_VERIFICATION_TOKEN", status_code=400)
    try:
        expires = datetime.fromisoformat(row["expires_at"])
    except ValueError as exc:
        raise APIError("验证链接无效或已过期", code="INVALID_VERIFICATION_TOKEN", status_code=400) from exc
    if expires <= datetime.now().astimezone():
        raise APIError("验证链接已过期，请重新发送验证邮件", code="VERIFICATION_TOKEN_EXPIRED", status_code=410)
    timestamp = now_iso()
    with transaction() as db:
        updated = db.execute(
            "UPDATE email_verification_tokens SET used_at = ? WHERE id = ? AND used_at IS NULL",
            (timestamp, row["id"]),
        )
        if updated.rowcount != 1:
            raise APIError("验证链接无效或已过期", code="INVALID_VERIFICATION_TOKEN", status_code=400)
        db.execute(
            "UPDATE auth_accounts SET email_verified_at = ?, "
            "active_verification_token_id = NULL, updated_at = ? WHERE id = ?",
            (timestamp, timestamp, row["account_id"]),
        )
    return {"email": row["email"], "verified": True}


def resend_verification(email_value: object) -> dict:
    email = normalize_email(email_value)
    # Consume the same dimensions for known and unknown addresses before any
    # account lookup, so the response cannot be used to enumerate accounts.
    _consume_account_action_limits("resend", email)
    account = query_one(
        "SELECT id, email_verified_at FROM auth_accounts WHERE lower(email) = ?", (email,)
    )
    # Always return the same response shape for unknown/verified accounts.
    if account is None or account["email_verified_at"]:
        return {"email": email, "sent": True}

    with transaction() as db:
        token, token_id = _create_token(db, int(account["id"]))
    try:
        if _discard_token_if_verified(int(account["id"]), token_id):
            return {"email": email, "sent": True}
    except sqlite3.OperationalError as exc:
        raise APIError(
            "验证状态暂时无法确认，请稍后再试",
            code="VERIFICATION_STATE_UNAVAILABLE",
            status_code=503,
        ) from exc
    try:
        send_verification_email(email, token)
    except MailDeliveryError as exc:
        # Do not leave an undelivered token behind, and do not invalidate the
        # previously delivered link when SMTP fails.
        with transaction() as db:
            db.execute(
                "DELETE FROM email_verification_tokens "
                "WHERE id = ? AND account_id = ? AND used_at IS NULL",
                (token_id, int(account["id"])),
            )
        raise APIError(
            "验证邮件暂时无法发送，请稍后重试",
            code="EMAIL_DELIVERY_FAILED",
            status_code=503,
        ) from exc

    # Only after the new email is sent successfully, activate it and
    # invalidate older links. Newer in-flight tokens are intentionally left
    # alone so a concurrent successful resend cannot zero out all links.
    try:
        with transaction() as db:
            _activate_token(db, int(account["id"]), token_id)
    except sqlite3.OperationalError as exc:
        raise APIError(
            "验证邮件已发送，但验证状态暂时无法更新，请稍后再试",
            code="VERIFICATION_STATE_UNAVAILABLE",
            status_code=503,
        ) from exc
    return {"email": email, "sent": True}


def authenticate(email_value: object, password_value: object) -> dict:
    email = normalize_email(email_value)
    password = str(password_value or "")
    row = query_one("SELECT * FROM auth_accounts WHERE lower(email) = ?", (email,))
    if row is None or not check_password_hash(row["password_hash"], password):
        raise APIError(_INVALID_LOGIN, code="INVALID_CREDENTIALS", status_code=401)
    if not row["email_verified_at"]:
        # Only reveal this after the password has been verified.
        raise APIError(
            "请先完成邮箱验证，再登录账户",
            code="EMAIL_NOT_VERIFIED",
            status_code=403,
        )
    return {"account_id": int(row["id"]), "user_id": int(row["user_id"]), "email": row["email"]}


def account_for_user(user_id: int) -> dict | None:
    row = query_one(
        "SELECT id, email, email_verified_at FROM auth_accounts WHERE user_id = ?",
        (user_id,),
    )
    if row is None:
        return None
    return {
        "id": int(row["id"]),
        "email": row["email"],
        "email_verified": bool(row["email_verified_at"]),
    }
