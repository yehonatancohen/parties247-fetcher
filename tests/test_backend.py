from __future__ import annotations

import logging
from typing import Any, Dict, List

import pytest

from jobs import backend


class DummyResponse:
    def __init__(self, status_code: int, payload: Dict[str, Any]) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = ""

    def json(self) -> Dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"error {self.status_code}")


class DummySession:
    def __init__(self, responses: List[DummyResponse]) -> None:
        self._responses = responses
        self.calls: List[Dict[str, Any]] = []

    def post(self, url: str, *, json=None, headers=None, timeout=None):
        self.calls.append({
            "url": url,
            "json": json,
            "headers": headers,
            "timeout": timeout,
        })
        if not self._responses:
            raise AssertionError("No more queued responses")
        return self._responses.pop(0)


def test_add_party_urls_posts_each_url(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = [
        DummyResponse(200, {"token": "abc"}),
        DummyResponse(200, {"status": "ok", "url": "https://first"}),
        DummyResponse(200, {"status": "ok", "url": "https://second"}),
    ]
    session = DummySession(responses)
    monkeypatch.setattr(backend, "get_admin_password", lambda env_path=None: "secret")

    client = backend.PartiesAdminClient(session=session)
    result = client.add_party_urls(["https://first", "https://second"])

    assert result == [
        {
            "status": "ok",
            "url": "https://first",
            "status_code": 200,
            "detail": "Party added successfully",
        },
        {
            "status": "ok",
            "url": "https://second",
            "status_code": 200,
            "detail": "Party added successfully",
        },
    ]
    assert session.calls[0]["url"].endswith(backend.LOGIN_ENDPOINT)
    assert session.calls[1]["json"] == {"url": "https://first"}
    assert session.calls[2]["json"] == {"url": "https://second"}
    assert session.calls[1]["headers"]["Authorization"] == "Bearer abc"


def test_add_party_urls_logs_statuses(monkeypatch: pytest.MonkeyPatch, caplog):
    responses = [
        DummyResponse(200, {"token": "abc"}),
        DummyResponse(409, {"detail": "Already exists"}),
        DummyResponse(200, {"status": "ok"}),
    ]
    session = DummySession(responses)
    monkeypatch.setattr(backend, "get_admin_password", lambda env_path=None: "secret")
    caplog.set_level(logging.INFO, backend.LOGGER.name)

    client = backend.PartiesAdminClient(session=session)
    result = client.add_party_urls(["https://first", "https://second"])

    assert result[0]["status_code"] == 409
    assert result[0]["detail"] == "Already exists"
    assert result[1]["status_code"] == 200
    assert result[1]["detail"] == "Party added successfully"

    summary_logs = [
        record for record in caplog.records if "Party add statuses" in record.getMessage()
    ]
    assert summary_logs
    summary_message = summary_logs[-1].getMessage()
    assert "https://first: 409 - Already exists" in summary_message
    assert "https://second: 200 - Party added successfully" in summary_message
