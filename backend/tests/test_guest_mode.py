"""Guest bootstrap/access boundary tests (server side)."""

from __future__ import annotations

import re


def test_guest_bootstrap_is_public_and_marks_guest_mode(anonymous_client):
    response = anonymous_client.get("/guest")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "进入访客模式" in body
    token = re.search(r'name="csrf_token" value="([^"]+)"', body).group(1)
    switched = anonymous_client.post("/guest", data={"csrf_token": token})
    assert switched.status_code == 200
    body = switched.get_data(as_text=True)
    assert "window.__STUDYFLOW_GUEST__ = true" in body
    assert "/js/app.js" in body


def test_guest_still_cannot_call_account_apis_without_session(anonymous_client):
    assert anonymous_client.get("/api/meta").status_code == 401
    assert anonymous_client.post("/api/guest/import", json={}).status_code == 401
