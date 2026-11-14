"""Single-admin session authentication for StudyFlow.

The application intentionally has no user registration or accounts. One
password hash is configured in ``STUDYFLOW_PASSWORD_HASH`` and every page/API
except the login/logout endpoints requires an authenticated Flask session.
"""

from __future__ import annotations

import math
import secrets
import threading
import time
from collections import defaultdict, deque
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, current_app, redirect, request, send_from_directory, session, url_for
from werkzeug.security import check_password_hash

from .utils.responses import failure, success

_PUBLIC_STATIC_PREFIXES = ("/css/", "/js/", "/vendor/", "/assets/")
_PUBLIC_EXACT_PATHS = {
    "/login",
    "/logout",
    "/api/auth/login",
    "/api/auth/logout",
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
_AUTH_TIME_KEY = "auth_at"
_AUTH_NONCE_KEY = "auth_nonce"


class LoginRateLimiter:
    """Small in-process fixed-window limiter for failed admin logins.

    A single-user deployment is small enough for this to be useful without a
    new database table or external service. Gunicorn workers each have their
    own counter; the deployment docs mention this tradeoff.
    """

    def __init__(self, max_attempts: int, window_seconds: int):
        self.max_attempts = max(1, int(max_attempts))
        self.window_seconds = max(60, int(window_seconds))
        self._attempts: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        attempts = self._attempts[key]
        cutoff = now - self.window_seconds
        while attempts and attempts[0] <= cutoff:
            attempts.popleft()
        if not attempts:
            self._attempts.pop(key, None)
            return deque()
        return attempts

    def retry_after(self, key: str) -> int:
        now = time.monotonic()
        with self._lock:
            attempts = self._prune(key, now)
            if len(attempts) < self.max_attempts:
                return 0
            return max(1, math.ceil(self.window_seconds - (now - attempts[0])))

    def record_failure(self, key: str) -> int:
        now = time.monotonic()
        with self._lock:
            attempts = self._prune(key, now)
            attempts.append(now)
            self._attempts[key] = attempts
            if len(attempts) < self.max_attempts:
                return 0
            return max(1, math.ceil(self.window_seconds - (now - attempts[0])))

    def clear(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._attempts.clear()


def reset_login_limits(app: Flask) -> None:
    limiter = app.extensions.get("studyflow_login_limiter")
    if limiter:
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
    return session.get(_SESSION_KEY) is True and not _expired()


def _establish_session() -> None:
    # Clear first so pre-login session values cannot survive authentication.
    session.clear()
    session.permanent = True
    session[_SESSION_KEY] = True
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


def _attempt(password: str) -> tuple[bool, int]:
    """Return (ok, retry_after). Never reveals whether config/hash is absent."""
    limiter = _limiter()
    key = _client_key()
    retry = limiter.retry_after(key)
    if retry:
        return False, retry
    stored = str(current_app.config.get("STUDYFLOW_PASSWORD_HASH") or "")
    try:
        valid = bool(stored) and check_password_hash(stored, password)
    except (ValueError, TypeError):
        valid = False
    if not valid:
        limiter.record_failure(key)
        return False, 0
    limiter.clear(key)
    _establish_session()
    return True, 0


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
        password = request.form.get("password", "")
        next_path = _safe_next(request.form.get("next"))
        ok, retry = _attempt(password)
        if retry:
            return redirect(
                url_for("login_page", error="rate", next=next_path)
            )
        if not ok:
            return redirect(
                url_for("login_page", error="invalid", next=next_path)
            )
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
        if not isinstance(password, str) or not password:
            return failure("请输入管理员密码。", code="VALIDATION_ERROR", status=400)
        ok, retry = _attempt(password)
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
