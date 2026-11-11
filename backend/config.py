"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
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
    APP_VERSION = "0.7.0-mvp"
    SECRET_KEY = os.getenv("SECRET_KEY", "studyflow-dev-secret-change-me")

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
    AI_VISION_BASE_URL = os.getenv(
        "AI_VISION_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ).rstrip("/")
    AI_VISION_MODEL = os.getenv("AI_VISION_MODEL", "qwen-vl-max")

    JSON_SORT_KEYS = False
