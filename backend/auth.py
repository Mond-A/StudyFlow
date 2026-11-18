"""Session authentication for StudyFlow.

Email accounts are the primary identity. A legacy password login remains
available only while no email account exists, so an existing single-user
database can be upgraded without locking the operator out. Once any email
account exists, all normal logins go through email verification.
"""

from __future__ import annotations

import hashlib
import math
import secrets
import time
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, current_app, has_app_context, redirect, request, send_from_directory, session, url_for
from werkzeug.security import check_password_hash

from .accounts import (
    authenticate,
    register_account,
    resend_verification,
    verify_email_token,
)
from .db import get_db, query_one
from .utils.exceptions import APIError
from .utils.responses import failure, success

_PUBLIC_STATIC_PREFIXES = ("/css/", "/js/", "/vendor/", "/assets/")
_PUBLIC_EXACT_PATHS = {
    "/login",
    "/logout",
    "/guest",
    "/verify-email",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/register",
    "/api/auth/resend-verification",
    "/api/auth/verify-email",
    "/favicon.ico",
}
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_WEAK_SECRETS = {
    "studyflow-dev-secret-change-me",
    "please-change-this-to-a-random-string",
    "changeme",
    "change-me",
    "secret",
}
_SESSION_KEY = "authenticated"
_SESSION_USER_KEY = "user_id"
_SESSION_ACCOUNT_KEY = "account_id"
_AUTH_TIME_KEY = "auth_at"
_AUTH_NONCE_KEY = "auth_nonce"


def _rate_limit_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


class LoginRateLimiter:
    """Fixed-window limiter shared by all Gunicorn workers via SQLite.

    SQLite is already the application database, so no extra service is needed.
    Only a SHA-256 of the IP/email key is stored; raw client identifiers never
    enter the table. ``BEGIN IMMEDIATE`` serializes the read-modify-write
    across workers, which keeps the effective limit equal to the configured
    value instead of multiplying it by the worker count.
    """

    def __init__(self, max_attempts: int, window_seconds: int):
        self.max_attempts = max(1, int(max_attempts))
        self.window_seconds = max(60, int(window_seconds))

    def retry_after(self, key: str) -> int:
        now = time.time()
        row = get_db().execute(
            "SELECT attempts, window_started FROM login_rate_limits WHERE key_hash = ?",
            (_rate_limit_key(key),),
        ).fetchone()
        if row is None:
            return 0
        elapsed = now - float(row["window_started"])
        if elapsed >= self.window_seconds or int(row["attempts"]) < self.max_attempts:
            return 0
        return max(1, math.ceil(self.window_seconds - elapsed))

    def record_failure(self, key: str) -> int:
        now = time.time()
        key_hash = _rate_limit_key(key)
        db = get_db()
        try:
            # Serialize the read-modify-write across processes sharing SQLite.
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT attempts, window_started FROM login_rate_limits WHERE key_hash = ?",
                (key_hash,),
            ).fetchone()
            if row is None or now - float(row["window_started"]) >= self.window_seconds:
                attempts = 1
                started = now
            else:
                attempts = int(row["attempts"]) + 1
                started = float(row["window_started"])
            db.execute(
                """
                INSERT INTO login_rate_limits (key_hash, attempts, window_started)
                VALUES (?, ?, ?)
                ON CONFLICT(key_hash) DO UPDATE SET
                    attempts = excluded.attempts,
                    window_started = excluded.window_started
                """,
                (key_hash, attempts, started),
            )
            # Opportunistically remove rows whose window has expired.
            db.execute(
                "DELETE FROM login_rate_limits WHERE window_started < ?",
                (now - self.window_seconds,),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        if attempts < self.max_attempts:
            return 0
        return max(1, math.ceil(self.window_seconds - (now - started)))

    def clear(self, key: str) -> None:
        db = get_db()
        db.execute(
            "DELETE FROM login_rate_limits WHERE key_hash = ?",
            (_rate_limit_key(key),),
        )
        db.commit()

    def reset(self) -> None:
        db = get_db()
        db.execute("DELETE FROM login_rate_limits")
        db.commit()


def reset_login_limits(app: Flask) -> None:
    limiter = app.extensions.get("studyflow_login_limiter")
    if not limiter:
        return
    if has_app_context():
        limiter.reset()
        return
    with app.app_context():
        limiter.reset()


def _limiter() -> LoginRateLimiter:
    return current_app.extensions["studyflow_login_limiter"]


def _client_key() -> str:
    return request.remote_addr or "unknown"


def _is_api(path: str) -> bool:
    return path.startswith("/api/")


def _is_public(path: str) -> bool:
    if path in _PUBLIC_EXACT_PATHS:
        return True
    return path.startswith(_PUBLIC_STATIC_PREFIXES)


def _safe_next(raw: object) -> str:
    if not isinstance(raw, str):
        return "/"
    value = raw.strip()
    if not value.startswith("/") or value.startswith("//") or "\\" in value:
        return "/"
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc:
        return "/"
    if value.startswith("/login"):
        return "/"
    return value


def _same_origin() -> bool:
    """Return False for an explicit cross-site Origin/Referer.

    SameSite=Lax already blocks cross-site session cookies. This second check
    protects JSON writes and logout from an explicitly cross-origin request.
    Requests without browser Origin/Referer headers (CLI, tests) are allowed
    and still require the session cookie.
    """
    origin = request.headers.get("Origin")
    target = origin or request.headers.get("Referer")
    if not target:
        return True
    if target == "null":
        return False
    parsed = urlsplit(target)
    host = request.host.lower()
    return bool(parsed.netloc) and parsed.netloc.lower() == host


def _expired() -> bool:
    raw = session.get(_AUTH_TIME_KEY)
    try:
        issued = float(raw)
    except (TypeError, ValueError):
        return True
    lifetime = current_app.config["PERMANENT_SESSION_LIFETIME"].total_seconds()
    return (time.time() - issued) > lifetime


def _session_valid() -> bool:
    user_id = session.get(_SESSION_USER_KEY)
    return (
        session.get(_SESSION_KEY) is True
        and isinstance(user_id, int)
        and user_id > 0
        and not _expired()
    )


def _establish_session(user_id: int, account_id: int | None = None) -> None:
    # Clear first so pre-login session values cannot survive authentication.
    session.clear()
    session.permanent = True
    session[_SESSION_KEY] = True
    session[_SESSION_USER_KEY] = int(user_id)
    if account_id is not None:
        session[_SESSION_ACCOUNT_KEY] = int(account_id)
    session[_AUTH_TIME_KEY] = int(time.time())
    session[_AUTH_NONCE_KEY] = secrets.token_urlsafe(24)
    session.modified = True


def _clear_session() -> None:
    session.clear()
    session.modified = True


def _unauthorized():
    if _is_api(request.path):
        response = failure(
            "请先登录 StudyFlow。",
            code="AUTH_REQUIRED",
            status=401,
        )
        response.headers["WWW-Authenticate"] = "Session"
        return response
    return redirect(url_for("login_page", next=request.full_path if request.query_string else request.path))


def _forbidden():
    if _is_api(request.path):
        return failure("请求来源校验失败。", code="CSRF_REJECTED", status=403)
    return ("请求来源校验失败。", 403)


def _check_origin_for_unsafe() -> object | None:
    if request.method in _SAFE_METHODS:
        return None
    if _same_origin():
        return None
    return _forbidden()


def _locked_response(retry_after: int):
    response = failure(
        "登录尝试过于频繁，请稍后再试。",
        code="LOGIN_RATE_LIMITED",
        status=429,
    )
    response.headers["Retry-After"] = str(retry_after)
    return response


def _legacy_allowed() -> bool:
    """The old password login is only a pre-migration bridge."""
    row = query_one("SELECT COUNT(*) AS count FROM auth_accounts")
    return bool(row and int(row["count"]) == 0)


def _legacy_attempt(password: str) -> tuple[bool, int]:
    """Return (ok, retry_after) for the transitional admin login."""
    limiter = _limiter()
    key = _client_key()
    retry = limiter.retry_after(key)
    if retry:
        return False, retry
    if not _legacy_allowed():
        return False, 0
    stored = str(current_app.config.get("STUDYFLOW_PASSWORD_HASH") or "")
    try:
        valid = bool(stored) and check_password_hash(stored, password)
    except (ValueError, TypeError):
        valid = False
    if not valid:
        limiter.record_failure(key)
        return False, 0
    user = query_one("SELECT id FROM users WHERE username = 'student' ORDER BY id LIMIT 1")
    if user is None:
        limiter.record_failure(key)
        return False, 0
    limiter.clear(key)
    _establish_session(int(user["id"]))
    return True, 0


def _email_attempt(email: str, password: str) -> tuple[dict | None, int]:
    limiter = _limiter()
    key = f"{_client_key()}|email|{email.lower()}"
    retry = limiter.retry_after(key)
    if retry:
        return None, retry
    try:
        account = authenticate(email, password)
    except APIError as error:
        if error.code == "INVALID_CREDENTIALS":
            limiter.record_failure(key)
        raise
    limiter.clear(key)
    _establish_session(account["user_id"], account["account_id"])
    return account, 0


def _api_error(error: APIError):
    return failure(
        error.message,
        code=error.code,
        status=error.status_code,
        details=error.details,
    )


def _validate_security_config(app: Flask) -> None:
    secret = str(app.config.get("SECRET_KEY") or "").strip()
    if not secret or secret in _WEAK_SECRETS or len(secret) < 32:
        raise RuntimeError(
            "SECRET_KEY is missing or too weak. Set a random 32+ character "
            "SECRET_KEY in .env; generate one with: "
            "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )
    password_hash = str(app.config.get("STUDYFLOW_PASSWORD_HASH") or "").strip()
    if not password_hash or password_hash.count("$") < 2:
        raise RuntimeError(
            "STUDYFLOW_PASSWORD_HASH is missing or invalid. Generate one with "
            "`python scripts/hash_password.py` and set it in .env. "
            "Plaintext passwords are not accepted."
        )
    same_site = str(app.config.get("SESSION_COOKIE_SAMESITE") or "").lower()
    if same_site not in {"lax", "strict", "none"}:
        raise RuntimeError("SESSION_COOKIE_SAMESITE must be Lax, Strict, or None.")
    if same_site == "none" and not app.config.get("SESSION_COOKIE_SECURE"):
        raise RuntimeError(
            "SESSION_COOKIE_SAMESITE=None requires SESSION_COOKIE_SECURE=true."
        )


def init_auth(app: Flask) -> None:
    _validate_security_config(app)
    app.extensions["studyflow_login_limiter"] = LoginRateLimiter(
        app.config["LOGIN_MAX_ATTEMPTS"],
        app.config["LOGIN_WINDOW_SECONDS"],
    )

    @app.before_request
    def enforce_auth():
        public = _is_public(request.path)
        if public:
            if request.method not in _SAFE_METHODS and not _same_origin():
                return _forbidden()
            return None

        if _session_valid():
            return _check_origin_for_unsafe()

        return _unauthorized()

    @app.get("/login")
    def login_page():
        if _session_valid():
            return redirect(_safe_next(request.args.get("next")))
        frontend = Path(current_app.config["FRONTEND_DIR"])
        if not (frontend / "login.html").is_file():
            return ("登录页面缺失。", 500)
        response = send_from_directory(frontend, "login.html")
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.post("/login")
    def login_form():
        origin_failure = _check_origin_for_unsafe()
        if origin_failure is not None:
            return origin_failure
        email = str(request.form.get("email", "")).strip()
        password = request.form.get("password", "")
        next_path = _safe_next(request.form.get("next"))
        if email:
            try:
                _email_attempt(email, password)
            except APIError as error:
                code = "unverified" if error.code == "EMAIL_NOT_VERIFIED" else "invalid"
                return redirect(url_for("login_page", error=code, next=next_path))
            return redirect(next_path)
        ok, retry = _legacy_attempt(password)
        if retry:
            return redirect(url_for("login_page", error="rate", next=next_path))
        if not ok:
            return redirect(url_for("login_page", error="invalid", next=next_path))
        return redirect(next_path)

    @app.post("/logout")
    def logout_form():
        origin_failure = _check_origin_for_unsafe()
        if origin_failure is not None:
            return origin_failure
        _clear_session()
        return redirect(url_for("login_page"))

    @app.post("/api/auth/login")
    def api_login():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return failure("请求必须使用 JSON。", code="INVALID_REQUEST", status=400)
        password = payload.get("password")
        email = str(payload.get("email", "")).strip()
        if not isinstance(password, str) or not password:
            return failure("请输入密码。", code="VALIDATION_ERROR", status=400)
        if email:
            try:
                account, retry = _email_attempt(email, password)
            except APIError as error:
                return _api_error(error)
            if retry:
                return _locked_response(retry)
            return success(
                {
                    "redirect": _safe_next(payload.get("next")),
                    "email": account["email"],
                },
                message="登录成功",
            )
        ok, retry = _legacy_attempt(password)
        if retry:
            return _locked_response(retry)
        if not ok:
            return failure(
                "密码错误，请重试。",
                code="INVALID_CREDENTIALS",
                status=401,
            )
        return success(
            {"redirect": _safe_next(payload.get("next"))},
            message="登录成功",
        )

    @app.post("/api/auth/register")
    def api_register():
        origin_failure = _check_origin_for_unsafe()
        if origin_failure is not None:
            return origin_failure
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return failure("请求必须使用 JSON。", code="INVALID_REQUEST", status=400)
        try:
            result = register_account(
                payload.get("email"),
                payload.get("password"),
                payload.get("display_name", ""),
            )
        except APIError as error:
            return _api_error(error)
        return success(
            result,
            status=201,
            message="账户已创建，请查收验证邮件。",
        )

    @app.post("/api/auth/resend-verification")
    def api_resend_verification():
        origin_failure = _check_origin_for_unsafe()
        if origin_failure is not None:
            return origin_failure
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return failure("请求必须使用 JSON。", code="INVALID_REQUEST", status=400)
        try:
            result = resend_verification(payload.get("email"))
        except APIError as error:
            return _api_error(error)
        return success(result, message="如果该邮箱等待验证，验证邮件已发送。")

    @app.post("/api/auth/verify-email")
    def api_verify_email():
        origin_failure = _check_origin_for_unsafe()
        if origin_failure is not None:
            return origin_failure
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return failure("请求必须使用 JSON。", code="INVALID_REQUEST", status=400)
        try:
            result = verify_email_token(payload.get("token"))
        except APIError as error:
            return _api_error(error)
        return success(result, message="邮箱验证成功。")

    @app.get("/verify-email")
    def verify_email_page():
        token = request.args.get("token", "")
        try:
            verify_email_token(token)
        except APIError:
            return redirect("/login?verified=0")
        return redirect("/login?verified=1")

    @app.post("/api/auth/logout")
    def api_logout():
        origin_failure = _check_origin_for_unsafe()
        if origin_failure is not None:
            return origin_failure
        _clear_session()
        return success({"redirect": "/login"}, message="已退出登录")

    app.logger.info(
        "Authentication enabled (session lifetime=%ss, login attempts=%s/%ss).",
        int(app.config["PERMANENT_SESSION_LIFETIME"].total_seconds()),
        app.config["LOGIN_MAX_ATTEMPTS"],
        app.config["LOGIN_WINDOW_SECONDS"],
    )
