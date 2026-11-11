"""Timezone-aware date helpers used by API services and seed data."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import current_app, has_app_context

DEFAULT_TIMEZONE = "Asia/Shanghai"


def get_timezone():
    name = DEFAULT_TIMEZONE
    if has_app_context():
        name = current_app.config.get("TIMEZONE", DEFAULT_TIMEZONE)
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(DEFAULT_TIMEZONE)


def now_local() -> datetime:
    return datetime.now(get_timezone()).replace(microsecond=0)


def now_iso() -> str:
    return now_local().isoformat()


def today_iso() -> str:
    return now_local().date().isoformat()


def iso_date(day: date) -> str:
    return day.isoformat()


def parse_date(value: str, field: str = "date") -> date:
    """Parse ISO date with a user-friendly validation error."""
    from .exceptions import APIError

    if not isinstance(value, str) or not value.strip():
        raise APIError(f"{field} 不能为空", code="VALIDATION_ERROR", status_code=400)
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise APIError(
            f"{field} 格式应为 YYYY-MM-DD", code="VALIDATION_ERROR", status_code=400
        ) from exc


def parse_time(value: str, field: str = "time") -> str:
    from .exceptions import APIError

    try:
        parsed = datetime.strptime(str(value).strip(), "%H:%M")
    except (TypeError, ValueError) as exc:
        raise APIError(
            f"{field} 格式应为 HH:MM", code="VALIDATION_ERROR", status_code=400
        ) from exc
    return parsed.strftime("%H:%M")


def add_minutes_to_time(value: str, minutes: int) -> str:
    start = datetime.strptime(value, "%H:%M")
    return (start + timedelta(minutes=int(minutes))).strftime("%H:%M")


def days_ago(days: int) -> date:
    return now_local().date() - timedelta(days=days)


def date_range_for_days(days: int) -> tuple[date, date]:
    end = now_local().date()
    return end - timedelta(days=max(0, days - 1)), end


def greeting_for_now() -> str:
    hour = now_local().hour
    if hour < 5:
        return "夜深了"
    if hour < 11:
        return "早上好"
    if hour < 14:
        return "中午好"
    if hour < 18:
        return "下午好"
    return "晚上好"


def human_date(day: date) -> str:
    return f"{day.month}月{day.day}日"


def week_start(day: date | None = None) -> date:
    target = day or now_local().date()
    return target - timedelta(days=target.weekday())
