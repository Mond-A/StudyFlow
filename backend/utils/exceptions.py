"""Typed API exceptions with a single JSON error shape."""

from __future__ import annotations


class APIError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str = "BAD_REQUEST",
        status_code: int = 400,
        details=None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details

    def to_dict(self) -> dict:
        error = {"code": self.code, "message": self.message}
        if self.details is not None:
            error["details"] = self.details
        return error


class NotFound(APIError):
    def __init__(self, message: str = "请求的资源不存在", *, code: str = "NOT_FOUND"):
        super().__init__(message, code=code, status_code=404)


class AIServiceError(APIError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "AI_ERROR",
        status_code: int = 502,
        details=None,
    ):
        super().__init__(message, code=code, status_code=status_code, details=details)
