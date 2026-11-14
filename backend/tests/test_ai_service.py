"""Unit tests for the live AI gateway transport/JSON retry logic.

These use a fake HTTP session, not a real external API. The project README
explicitly records that no live third-party AI call was executed without keys.
"""

from __future__ import annotations

import pytest

from backend.services.ai_service import AIService
from backend.utils.exceptions import AIServiceError

VISION_DATA_URL = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB"


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
        "AI_VISION_BASE_URL": "https://example.invalid/compatible-mode/v1",
        "AI_VISION_MODEL": "qwen3.8-flash",
        "AI_TIMEOUT": 10,
        "AI_MAX_RETRIES": 2,
    }


def vision_live_config():
    config = live_config()
    config["AI_VISION_API_KEY"] = "server-only-vision-test-key"
    return config


def chat_payload(content, model=None):
    payload = {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 34},
    }
    if model:
        payload["model"] = model
    return payload


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


def test_upstream_error_details_redact_key_and_bearer_value():
    secret = "server-only-test-key"
    session = FakeSession(
        [
            FakeResponse(
                400,
                {
                    "error": {
                        "message": f"bad request for key {secret}; header=Bearer {secret}"
                    }
                },
            )
        ]
    )
    service = AIService(live_config(), http_session=session)
    with pytest.raises(AIServiceError) as error:
        service.complete_json(
            capability="text",
            system_prompt="Return JSON.",
            user_prompt="Do the task.",
        )
    assert error.value.code == "AI_REQUEST_REJECTED"
    assert secret not in str(error.value.details)
    assert "[redacted]" in str(error.value.details)
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


def test_qwen_multimodal_payload_uses_image_url_part_not_a_path():
    session = FakeSession(
        [
            FakeResponse(
                200,
                chat_payload(
                    '{"shape": "circle", "color": "red"}',
                    model="qwen3.8-flash",
                ),
            )
        ]
    )
    service = AIService(vision_live_config(), http_session=session)
    result, usage, info = service.complete_json(
        capability="vision",
        system_prompt="Return only JSON.",
        user_prompt="Describe the test image as JSON.",
        images=[VISION_DATA_URL],
        validator=lambda raw: raw,
        temperature=0,
    )

    assert result == {"shape": "circle", "color": "red"}
    assert info["provider"] == "qwen"
    assert info["model"] == "qwen3.8-flash"
    assert usage["response_model"] == "qwen3.8-flash"
    call = session.calls[0]
    assert call["url"] == (
        "https://example.invalid/compatible-mode/v1/chat/completions"
    )
    sent = call["json"]
    assert sent["model"] == "qwen3.8-flash"
    parts = sent["messages"][1]["content"]
    assert isinstance(parts, list)
    assert parts[0]["type"] == "text"
    assert parts[1] == {"type": "image_url", "image_url": {"url": VISION_DATA_URL}}
    # The local or remote path must not appear as a plain text part.
    assert "/uploads/" not in str(parts[0])
    assert all(part["type"] != "text" or VISION_DATA_URL not in part["text"] for part in parts)


def test_qwen_vision_rejects_filesystem_path_as_image_input():
    session = FakeSession([])
    service = AIService(vision_live_config(), http_session=session)
    with pytest.raises(AIServiceError) as error:
        service.complete_json(
            capability="vision",
            system_prompt="Return JSON.",
            user_prompt="Describe this image.",
            images=["data/uploads/photo.png"],
        )
    assert error.value.code == "IMAGE_FORMAT_ERROR"
    assert session.calls == []


def test_vision_base_url_is_required_from_environment():
    config = vision_live_config()
    config["AI_VISION_BASE_URL"] = ""
    service = AIService(config)
    status = service.status()["vision"]
    assert status["config_complete"] is False
    assert "AI_VISION_BASE_URL" in status["missing_env"]
    assert status["base_url_configured"] is False
    assert status["effective_mode"] == "unavailable"

    with pytest.raises(AIServiceError) as error:
        service.resolve_mode("vision")
    assert error.value.code == "AI_CONFIG_ERROR"
    assert "AI_VISION_BASE_URL" in error.value.message

    with pytest.raises(AIServiceError) as error:
        service.probe("vision")
    assert error.value.code == "AI_CONFIG_ERROR"


def test_qwen_model_defaults_to_requested_name_and_environment_can_override():
    config = vision_live_config()
    config.pop("AI_VISION_MODEL")
    service = AIService(config)
    assert service.status()["vision"]["model"] == "qwen3.8-flash"

    config["AI_VISION_MODEL"] = "qwen-custom-vision-model"
    service = AIService(config)
    assert service.status()["vision"]["model"] == "qwen-custom-vision-model"


def test_probe_returns_real_response_model_and_rejects_demo_mode():
    session = FakeSession(
        [
            FakeResponse(
                200,
                chat_payload('{"pong": true}', model="qwen3.8-flash-2026-xx-xx"),
            )
        ]
    )
    service = AIService(vision_live_config(), http_session=session)
    result = service.probe("vision")
    assert result["configured_model"] == "qwen3.8-flash"
    assert result["response_model"] == "qwen3.8-flash-2026-xx-xx"
    assert result["provider"] == "qwen"

    demo_config = vision_live_config()
    demo_config["AI_VISION_API_KEY"] = ""
    demo_service = AIService(demo_config)
    with pytest.raises(AIServiceError) as error:
        demo_service.probe("vision")
    assert error.value.code == "AI_NOT_LIVE"
