"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(ENV_PATH)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _resolve_path(raw: str, default: str) -> Path:
    value = Path(raw or default).expanduser()
    if not value.is_absolute():
        value = PROJECT_ROOT / value
    return value.resolve()


class Config:
    APP_NAME = "StudyFlow"
    APP_VERSION = "1.1.0"

    # Authentication is mandatory. These deliberately have no usable default:
    # create_app() fails with a clear error until both are supplied.
    SECRET_KEY = os.getenv("SECRET_KEY", "").strip()
    STUDYFLOW_PASSWORD_HASH = os.getenv("STUDYFLOW_PASSWORD_HASH", "").strip()

    SESSION_COOKIE_NAME = "studyflow_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax").strip() or "Lax"
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", False)
    PERMANENT_SESSION_LIFETIME = timedelta(
        hours=max(1, min(_env_int("SESSION_LIFETIME_HOURS", 12), 168))
    )
    SESSION_REFRESH_EACH_REQUEST = True

    LOGIN_MAX_ATTEMPTS = max(1, min(_env_int("LOGIN_MAX_ATTEMPTS", 5), 20))
    LOGIN_WINDOW_SECONDS = max(60, min(_env_int("LOGIN_WINDOW_SECONDS", 900), 86400))
    TRUST_PROXY = _env_bool("TRUST_PROXY", False)

    # Iteration 1 email accounts. Console is for local development only; a
    # deployment must set MAIL_BACKEND=smtp and the SMTP values explicitly.
    MAIL_BACKEND = os.getenv("MAIL_BACKEND", "console").strip().lower() or "console"
    MAIL_FROM = os.getenv("MAIL_FROM", "StudyFlow <no-reply@localhost>").strip()
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:5000").strip().rstrip("/")
    SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
    SMTP_PORT = max(1, _env_int("SMTP_PORT", 587))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "").strip()
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_USE_TLS = _env_bool("SMTP_USE_TLS", True)
    SMTP_USE_SSL = _env_bool("SMTP_USE_SSL", False)
    EMAIL_VERIFICATION_HOURS = max(1, min(_env_int("EMAIL_VERIFICATION_HOURS", 24), 168))
    PASSWORD_MIN_LENGTH = max(10, min(_env_int("PASSWORD_MIN_LENGTH", 12), 64))

    FRONTEND_DIR = PROJECT_ROOT / "frontend"
    DATABASE_PATH = _resolve_path(os.getenv("DATABASE_PATH", ""), "data/studyflow.db")
    UPLOAD_DIR = _resolve_path(os.getenv("UPLOAD_DIR", ""), "data/uploads")
    TIMEZONE = os.getenv("TIMEZONE", "Asia/Shanghai")

    MAX_CONTENT_LENGTH = 12 * 1024 * 1024  # 12 MB request cap
    MAX_IMAGE_BYTES = 8 * 1024 * 1024
    ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

    SEED_DEMO = _env_bool("SEED_DEMO", True)
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "").split(",")
        if origin.strip()
    ]

    # auto | on | off
    AI_DEMO_MODE = os.getenv("AI_DEMO_MODE", "auto").strip().lower() or "auto"
    AI_TIMEOUT = _env_int("AI_TIMEOUT", 60)
    AI_MAX_RETRIES = max(0, min(_env_int("AI_MAX_RETRIES", 2), 4))

    AI_TEXT_PROVIDER = os.getenv("AI_TEXT_PROVIDER", "deepseek")
    AI_TEXT_API_KEY = os.getenv("AI_TEXT_API_KEY", "")
    AI_TEXT_BASE_URL = os.getenv("AI_TEXT_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
    AI_TEXT_MODEL = os.getenv("AI_TEXT_MODEL", "deepseek-chat")

    AI_VISION_PROVIDER = os.getenv("AI_VISION_PROVIDER", "qwen")
    AI_VISION_API_KEY = os.getenv("AI_VISION_API_KEY", "")
    # Base URL is deliberately required from the environment. See
    # AI_VISION_BASE_URL in .env.example (DashScope OpenAI-compatible mode).
    AI_VISION_BASE_URL = os.getenv("AI_VISION_BASE_URL", "").strip().rstrip("/")
    AI_VISION_MODEL = (
        os.getenv("AI_VISION_MODEL", "").strip() or "qwen3.8-flash"
    )

    JSON_SORT_KEYS = False
