"""Shared pytest fixtures for the StudyFlow API test suite."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from backend.app import create_app


@pytest.fixture()
def app_factory(tmp_path):
    counter = {"value": 0}

    def factory(**overrides):
        counter["value"] += 1
        database = tmp_path / f"studyflow-test-{counter['value']}.db"
        uploads = tmp_path / f"uploads-{counter['value']}"
        config = {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "DATABASE_PATH": str(database),
            "UPLOAD_DIR": str(uploads),
            "SEED_DEMO": False,
            "AI_DEMO_MODE": "auto",
            "AI_TEXT_API_KEY": "",
            "AI_VISION_API_KEY": "",
            "TIMEZONE": "Asia/Shanghai",
        }
        config.update(overrides)
        return create_app(config)

    return factory


@pytest.fixture()
def app(app_factory):
    return app_factory()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def image_file():
    """A valid PNG image created in memory for upload/vision tests."""
    buffer = io.BytesIO()
    image = Image.new("RGB", (320, 240), (244, 248, 255))
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


@pytest.fixture()
def upload_image(client, image_file):
    def _upload(filename="homework.png"):
        image_file.seek(0)
        response = client.post(
            "/api/uploads",
            data={"image": (image_file, filename)},
            content_type="multipart/form-data",
        )
        data = response.get_json()
        assert response.status_code == 201, data
        return data["data"]

    return _upload


@pytest.fixture()
def sample_task(client):
    response = client.post(
        "/api/tasks",
        json={
            "title": "完成数学练习",
            "subject": "数学",
            "estimated_minutes": 40,
            "difficulty": 3,
            "priority": 1,
        },
    )
    assert response.status_code == 201
    return response.get_json()["data"]


@pytest.fixture()
def sample_note(client):
    response = client.post(
        "/api/notes",
        json={
            "title": "二次函数基础",
            "subject": "数学",
            "content_markdown": (
                "# 二次函数\n\n## 顶点公式\n\n"
                "$$x = -\\frac{b}{2a}$$\n\n"
                "## 判别式\n\n$\\Delta = b^2 - 4ac$"
            ),
        },
    )
    assert response.status_code == 201
    return response.get_json()["data"]


def assert_ok(response, expected_status: int = 200):
    payload = response.get_json()
    assert response.status_code == expected_status, payload
    assert payload["ok"] is True
    return payload
