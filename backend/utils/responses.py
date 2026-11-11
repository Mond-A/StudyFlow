"""Unified success/error response helpers."""

from __future__ import annotations

import logging
import traceback

from flask import jsonify, request
from werkzeug.exceptions import HTTPException

from .exceptions import APIError

logger = logging.getLogger("studyflow.api")


def success(data=None, *, status: int = 200, message: str | None = None, ai=None):
    payload: dict = {"ok": True, "data": data}
    if message:
        payload["message"] = message
    if ai is not None:
        payload["ai"] = ai
    response = jsonify(payload)
    response.status_code = status
    return response


def failure(message: str, *, code: str, status: int, details=None):
    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    response = jsonify({"ok": False, "error": error})
    response.status_code = status
    return response


def register_error_handlers(app):
    @app.errorhandler(APIError)
    def handle_api_error(err: APIError):
        return failure(
            err.message, code=err.code, status=err.status_code, details=err.details
        )

    @app.errorhandler(HTTPException)
    def handle_http_error(err: HTTPException):
        if request.path.startswith("/api/"):
            code_map = {
                404: "NOT_FOUND",
                405: "METHOD_NOT_ALLOWED",
                413: "PAYLOAD_TOO_LARGE",
                415: "UNSUPPORTED_MEDIA_TYPE",
            }
            return failure(
                err.description or err.name,
                code=code_map.get(err.code, "HTTP_ERROR"),
                status=err.code or 500,
            )
        return err

    @app.errorhandler(Exception)
    def handle_unexpected_error(err: Exception):
        logger.error("Unhandled error: %s\n%s", err, traceback.format_exc())
        if request.path.startswith("/api/"):
            return failure(
                "服务器内部错误，请稍后重试",
                code="INTERNAL_ERROR",
                status=500,
            )
        return failure("服务器内部错误", code="INTERNAL_ERROR", status=500)
