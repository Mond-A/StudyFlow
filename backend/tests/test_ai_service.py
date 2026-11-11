"""Unit tests for the live AI gateway transport/JSON retry logic.

These use a fake HTTP session, not a real external API. The project README
explicitly records that no live third-party AI call was executed without keys.
"""

from __future__ import annotations

import pytest

from backend.services.ai_service import AIService
from backend.utils.exceptions import AIServiceError


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return self.responses.pop(0)


def live_config():
    return {
        "AI_DEMO_MODE": "auto",
        "AI_TEXT_API_KEY": "server-only-test-key",
        "AI_TEXT_PROVIDER": "deepseek",
        "AI_TEXT_BASE_URL": "https://example.invalid/v1",
        "AI_TEXT_MODEL": "deepseek-chat",
        "AI_VISION_API_KEY": "",
        "AI_VISION_PROVIDER": "qwen",
        "AI_VISION_BASE_URL": "https://example.invalid/v1",
        "AI_VISION_MODEL": "qwen-vl-max",
        "AI_TIMEOUT": 10,
        "AI_MAX_RETRIES": 2,
    }


def chat_payload(content):
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 34},
    }


def test_live_json_pipeline_retries_malformed_output():
    session = FakeSession(
        [
            FakeResponse(200, chat_payload("this is not JSON at all")),
            FakeResponse(200, chat_payload('```json\n{"ok": true, "items": ["a"]}\n```')),
        ]
    )
    service = AIService(live_config(), http_session=session)
    result, usage, mode_info = service.complete_json(
        capability="text",
        system_prompt="Return JSON.",
        user_prompt="Do the task.",
        validator=lambda value: {**value, "validated": True},
    )
    assert result["ok"] is True
    assert result["validated"] is True
    assert usage["completion_tokens"] == 34
    assert mode_info["mode"] == "live"
    assert len(session.calls) == 2
    assert session.calls[0]["url"] == "https://example.invalid/v1/chat/completions"
    assert session.calls[0]["headers"]["Authorization"].startswith("Bearer ")


def test_live_json_pipeline_fails_after_limited_retries():
    session = FakeSession(
        [
            FakeResponse(200, chat_payload("nope")),
            FakeResponse(200, chat_payload("still nope")),
            FakeResponse(200, chat_payload("again nope")),
        ]
    )
    service = AIService(live_config(), http_session=session)
    with pytest.raises(AIServiceError) as error:
        service.complete_json(
            capability="text",
            system_prompt="Return JSON.",
            user_prompt="Do the task.",
        )
    assert error.value.code == "AI_INVALID_RESPONSE"
    assert len(session.calls) == 3


def test_authentication_error_does_not_leak_key():
    session = FakeSession([FakeResponse(401, {"error": {"message": "invalid key abc"}})])
    service = AIService(live_config(), http_session=session)
    with pytest.raises(AIServiceError) as error:
        service.complete_json(
            capability="text",
            system_prompt="Return JSON.",
            user_prompt="Do the task.",
        )
    assert error.value.code == "AI_AUTH_ERROR"
    assert "server-only-test-key" not in error.value.message
    # Auth failures are not retried.
    assert len(session.calls) == 1


def test_mode_resolution_auto_and_demo_override():
    config = live_config()
    config["AI_TEXT_API_KEY"] = ""
    service = AIService(config)
    status = service.status()
    assert status["text"]["effective_mode"] == "demo"
    assert status["vision"]["effective_mode"] == "demo"
    assert service.resolve_mode("text")["mode"] == "demo"

    config["AI_DEMO_MODE"] = "on"
    config["AI_TEXT_API_KEY"] = "some-key"
    service = AIService(config)
    assert service.resolve_mode("text")["mode"] == "demo"
