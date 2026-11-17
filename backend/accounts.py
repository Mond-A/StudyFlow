"""Email account registration, verification, and authentication primitives."""

from __future__ import annotations

import hashlib
import re
import secrets
import sqlite3
from datetime import datetime, timedelta

from flask import current_app
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db, query_one, transaction
from .mailer import MailDeliveryError, send_verification_email
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


def _issue_token(db, account_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = (
        datetime.now().astimezone()
        + timedelta(hours=int(current_app.config["EMAIL_VERIFICATION_HOURS"]))
    ).isoformat(timespec="seconds")
    db.execute(
        "UPDATE email_verification_tokens SET used_at = ? WHERE account_id = ? AND used_at IS NULL",
        (now_iso(), account_id),
    )
    db.execute(
        """
        INSERT INTO email_verification_tokens
            (account_id, token_hash, expires_at, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (account_id, _token_hash(token), expires_at, now_iso()),
    )
    return token


def register_account(email_value: object, password_value: object, display_value: object = "") -> dict:
    email = normalize_email(email_value)
    password = validate_password(password_value)
    display_name = _display_name(display_value, email)
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
            token = _issue_token(db, account_id)
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
               a.email, a.email_verified_at
        FROM email_verification_tokens t
        JOIN auth_accounts a ON a.id = t.account_id
        WHERE t.token_hash = ?
        """,
        (token_hash,),
    )
    if row is None or row["used_at"] or row["email_verified_at"]:
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
            "UPDATE auth_accounts SET email_verified_at = ?, updated_at = ? WHERE id = ?",
            (timestamp, timestamp, row["account_id"]),
        )
    return {"email": row["email"], "verified": True}


def resend_verification(email_value: object) -> dict:
    email = normalize_email(email_value)
    account = query_one(
        "SELECT id, email_verified_at FROM auth_accounts WHERE lower(email) = ?", (email,)
    )
    # Always return the same response shape for unknown/verified accounts.
    if account is None or account["email_verified_at"]:
        return {"email": email, "sent": True}
    with transaction() as db:
        token = _issue_token(db, int(account["id"]))
    try:
        send_verification_email(email, token)
    except MailDeliveryError as exc:
        raise APIError(
            "验证邮件暂时无法发送，请稍后重试",
            code="EMAIL_DELIVERY_FAILED",
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
