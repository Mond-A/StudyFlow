"""Small validation helpers keep route code declarative."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from flask import request

from .exceptions import APIError
from .timeutils import parse_date, parse_time


def json_body(*, required: bool = True) -> dict:
    payload = request.get_json(silent=True)
    if payload is None:
        if required:
            raise APIError(
                "请求体必须是 JSON，并设置 Content-Type: application/json",
                code="INVALID_CONTENT_TYPE",
                status_code=415,
            )
        return {}
    if not isinstance(payload, dict):
        raise APIError("JSON 请求体必须是对象", code="VALIDATION_ERROR", status_code=400)
    return payload


def text_field(
    data: dict,
    field: str,
    label: str,
    *,
    required: bool = False,
    default: str = "",
    max_length: int = 5000,
) -> str:
    if field not in data or data[field] is None:
        if required:
            raise APIError(f"{label}不能为空", code="VALIDATION_ERROR", status_code=400)
        return default
    value = data[field]
    if not isinstance(value, str):
        raise APIError(f"{label}必须是文本", code="VALIDATION_ERROR", status_code=400)
    value = value.strip()
    if required and not value:
        raise APIError(f"{label}不能为空", code="VALIDATION_ERROR", status_code=400)
    if len(value) > max_length:
        raise APIError(
            f"{label}不能超过 {max_length} 个字符",
            code="VALIDATION_ERROR",
            status_code=400,
        )
    return value


def int_field(
    data: dict,
    field: str,
    label: str,
    *,
    default: int | None = None,
    required: bool = False,
    minimum: int = 0,
    maximum: int = 1440,
) -> int | None:
    if data.get(field) in (None, ""):
        if required:
            raise APIError(f"{label}不能为空", code="VALIDATION_ERROR", status_code=400)
        return default
    try:
        value = int(data[field])
    except (TypeError, ValueError) as exc:
        raise APIError(f"{label}必须是整数", code="VALIDATION_ERROR", status_code=400) from exc
    if value < minimum or value > maximum:
        raise APIError(
            f"{label}必须在 {minimum} 到 {maximum} 之间",
            code="VALIDATION_ERROR",
            status_code=400,
        )
    return value


def float_field(
    data: dict,
    field: str,
    label: str,
    *,
    default: float | None = None,
    required: bool = False,
    minimum: float = 0,
    maximum: float = 100000,
) -> float | None:
    if data.get(field) in (None, ""):
        if required:
            raise APIError(f"{label}不能为空", code="VALIDATION_ERROR", status_code=400)
        return default
    try:
        value = float(data[field])
    except (TypeError, ValueError) as exc:
        raise APIError(f"{label}必须是数字", code="VALIDATION_ERROR", status_code=400) from exc
    if value < minimum or value > maximum:
        raise APIError(
            f"{label}必须在 {minimum} 到 {maximum} 之间",
            code="VALIDATION_ERROR",
            status_code=400,
        )
    return value


def date_field(
    data: dict,
    field: str,
    label: str,
    *,
    required: bool = False,
    default: str | None = None,
) -> str | None:
    value = data.get(field)
    if value in (None, ""):
        if required:
            raise APIError(f"{label}不能为空", code="VALIDATION_ERROR", status_code=400)
        return default
    return parse_date(str(value), label).isoformat()


def time_field(
    data: dict,
    field: str,
    label: str,
    *,
    default: str | None = None,
) -> str | None:
    value = data.get(field)
    if value in (None, ""):
        return default
    return parse_time(str(value), label)


def bool_field(data: dict, field: str, default: bool = False) -> bool:
    if field not in data or data[field] is None:
        return default
    value = data[field]
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return default


def choice_field(
    data: dict,
    field: str,
    label: str,
    choices: set[str] | tuple[str, ...],
    *,
    default: str | None = None,
) -> str | None:
    value = data.get(field)
    if value in (None, ""):
        return default
    if value not in choices:
        allowed = "、".join(sorted(choices))
        raise APIError(
            f"{label}必须是以下之一：{allowed}",
            code="VALIDATION_ERROR",
            status_code=400,
        )
    return value


def query_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = request.args.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise APIError(f"{name} 必须是整数", code="VALIDATION_ERROR", status_code=400) from exc
    return max(minimum, min(maximum, value))


def optional_datetime(value: Any, label: str) -> str | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise APIError(
            f"{label}必须是 ISO 时间格式", code="VALIDATION_ERROR", status_code=400
        ) from exc
    return parsed.replace(microsecond=0).isoformat()
