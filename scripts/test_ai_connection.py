#!/usr/bin/env python3
"""Opt-in real AI connectivity test for StudyFlow.

This script makes real, billable API requests when keys are present. It is not
part of the normal pytest suite.

Usage:
    python scripts/test_ai_connection.py
    python scripts/test_ai_connection.py --capability text
    python scripts/test_ai_connection.py --capability all
    python scripts/test_ai_connection.py --skip-image

The API key is loaded from .env / process environment and is never printed.
Exit codes:
    0  every requested live test passed
    1  at least one live request failed
    2  prerequisites were missing, or AI_DEMO_MODE prevented a live request
"""

from __future__ import annotations

import argparse
import base64
import io
import sys
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import Config  # noqa: E402
from backend.services.ai_service import AIService  # noqa: E402
from backend.utils.exceptions import AIServiceError  # noqa: E402

CONFIG_KEYS = (
    "AI_DEMO_MODE",
    "AI_TIMEOUT",
    "AI_MAX_RETRIES",
    "AI_TEXT_PROVIDER",
    "AI_TEXT_API_KEY",
    "AI_TEXT_BASE_URL",
    "AI_TEXT_MODEL",
    "AI_VISION_PROVIDER",
    "AI_VISION_API_KEY",
    "AI_VISION_BASE_URL",
    "AI_VISION_MODEL",
)


def make_service(config: dict | None = None) -> AIService:
    values = config or {key: getattr(Config, key, None) for key in CONFIG_KEYS}
    return AIService(values)


def safe_url(value: str) -> str:
    """Do not print credentials embedded in a URL or any query string."""
    if not value:
        return "(not set)"
    try:
        parts = urlsplit(value)
        host = parts.hostname or ""
        if parts.port:
            host += f":{parts.port}"
        return f"{parts.scheme}://{host}{parts.path}".rstrip("/")
    except ValueError:
        return "(invalid URL)"


def display_config(config: dict) -> None:
    print("AI configuration (secrets redacted):")
    for capability, prefix in (("vision", "AI_VISION"), ("text", "AI_TEXT")):
        key = config.get(f"{prefix}_API_KEY") or ""
        base_url = config.get(f"{prefix}_BASE_URL") or ""
        model = config.get(f"{prefix}_MODEL") or ""
        print(
            f"  {capability}: provider={config.get(f'{prefix}_PROVIDER') or '(not set)'} "
            f"model={model or '(not set)'} "
            f"base_url={safe_url(base_url)} "
            f"api_key={'SET (redacted)' if key else 'MISSING'}"
        )
    print(f"  AI_DEMO_MODE={config.get('AI_DEMO_MODE')}")


def create_test_image_data_url() -> str:
    """Create a deterministic red circle on a white background in memory."""
    image = Image.new("RGB", (320, 240), "white")
    draw = ImageDraw.Draw(image)
    draw.ellipse((80, 40, 240, 200), fill=(220, 38, 38))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def validate_red_circle(raw: dict) -> dict:
    shape = str(raw.get("shape", "")).strip().lower()
    color = str(raw.get("color", "")).strip().lower()
    if not shape or not color:
        raise ValueError("missing shape or color")
    is_circle = any(token in shape for token in ("circle", "round", "ellipse", "圆"))
    is_red = any(token in color for token in ("red", "红"))
    if not (is_circle and is_red):
        raise ValueError(f"unexpected image description: shape={shape!r}, color={color!r}")
    return {"shape": shape, "color": color}


def prerequisite_state(service: AIService, capability: str) -> str:
    status = service.status()[capability]
    env_prefix = "AI_VISION" if capability == "vision" else "AI_TEXT"
    if not status["configured"]:
        print(
            f"[SKIP] {capability}: {env_prefix}_API_KEY is not set. "
            "No external request was sent."
        )
        return "skipped"
    if not status["config_complete"]:
        print(
            f"[FAIL] {capability}: configuration incomplete; missing "
            f"{', '.join(status['missing_env'])}. No external request was sent."
        )
        return "failed"
    if status["effective_mode"] != "live":
        print(
            f"[SKIP] {capability}: effective_mode={status['effective_mode']} "
            f"(AI_DEMO_MODE={service.status()['policy']}). "
            "Set AI_DEMO_MODE=auto or off to run a live test."
        )
        return "skipped"
    return "ready"


def test_text_connectivity(service: AIService) -> bool:
    print("\n[1/1] Text API connectivity (JSON round-trip)…")
    try:
        result = service.probe("text")
    except AIServiceError as exc:
        print(f"[FAIL] text connectivity: {exc.code}: {exc.message}")
        return False
    print(
        "[PASS] text connectivity "
        f"provider={result['provider']} configured_model={result['configured_model']} "
        f"response_model={result.get('response_model') or '(not returned)'}"
    )
    return True


def test_vision_connectivity(service: AIService, *, skip_image: bool = False) -> bool:
    print("\n[1/2] Qwen vision endpoint connectivity (text-only JSON request)…")
    try:
        ping = service.probe("vision")
    except AIServiceError as exc:
        print(f"[FAIL] vision connectivity: {exc.code}: {exc.message}")
        print("Image test was NOT run because the connectivity step failed.")
        return False
    print(
        "[PASS] vision connectivity "
        f"provider={ping['provider']} configured_model={ping['configured_model']} "
        f"response_model={ping.get('response_model') or '(not returned)'}"
    )
    if skip_image:
        print("[SKIP] image input test (--skip-image).")
        return True

    print("\n[2/2] Qwen multimodal image input (data URL / image_url message)…")
    image_data_url = create_test_image_data_url()
    try:
        result, usage, info = service.complete_json(
            capability="vision",
            system_prompt="这是图片输入测试。只返回合法 JSON，不要输出 Markdown。",
            user_prompt=(
                "图片为白底，中央有一个纯色几何图形。"
                '只返回 JSON：{"shape":"circle|square|triangle|other",'
                '"color":"red|blue|green|yellow|black|white|other"}'
            ),
            images=[image_data_url],
            validator=validate_red_circle,
            temperature=0.0,
            max_tokens=256,
        )
    except AIServiceError as exc:
        print(f"[FAIL] image input: {exc.code}: {exc.message}")
        return False
    print(
        "[PASS] image input "
        f"provider={info['provider']} configured_model={info['model']} "
        f"response_model={usage.get('response_model') or '(not returned)'} "
        f"observed={result}"
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run real StudyFlow AI connectivity tests (billable API calls)."
    )
    parser.add_argument(
        "--capability",
        choices=("vision", "text", "all"),
        default="vision",
        help="Which capability to test. Default: vision (Qwen endpoint + image input).",
    )
    parser.add_argument(
        "--skip-image",
        action="store_true",
        help="For vision, only test endpoint connectivity; do not send an image.",
    )
    args = parser.parse_args()

    config = {key: getattr(Config, key, None) for key in CONFIG_KEYS}
    display_config(config)
    service = make_service(config)
    requested = ["vision", "text"] if args.capability == "all" else [args.capability]

    states = {capability: prerequisite_state(service, capability) for capability in requested}
    if any(state == "failed" for state in states.values()):
        print("\nResult: FAILED (configuration incomplete); no external request was sent.")
        return 1

    outcomes: dict[str, bool | None] = {}
    for capability in requested:
        if states[capability] != "ready":
            outcomes[capability] = None
            continue
        if capability == "vision":
            outcomes[capability] = test_vision_connectivity(
                service, skip_image=args.skip_image
            )
        else:
            outcomes[capability] = test_text_connectivity(service)

    if any(value is False for value in outcomes.values()):
        print("\nResult: FAILED (a real API request or image validation failed).")
        return 1
    if any(value is None for value in outcomes.values()):
        print("\nResult: SKIPPED (missing credentials or demo policy); no success claimed.")
        return 2
    print("\nResult: PASS (real API connectivity and requested image test succeeded).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
