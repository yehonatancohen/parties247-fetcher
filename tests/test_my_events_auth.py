from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from jobs import my_events


class FakeDriver:
    def __init__(self, cookies: List[Dict[str, Any]]) -> None:
        self.cookies = cookies
        self.calls: List[tuple[str, Any]] = []

    def get(self, url: str) -> None:
        self.calls.append(("get", url))

    def add_cookie(self, cookie: Dict[str, Any]) -> None:
        self.calls.append(("add_cookie", cookie))

    def execute_script(self, script: str, *args: Any) -> None:
        self.calls.append(("execute_script", script, *args))

    def refresh(self) -> None:
        self.calls.append(("refresh", None))

    def get_cookies(self) -> List[Dict[str, Any]]:
        self.calls.append(("get_cookies", None))
        return self.cookies

    def quit(self) -> None:
        self.calls.append(("quit", None))


def test_fetch_cookies_via_selenium_uses_webdriver_factory() -> None:
    cookies = [
        {"name": "session", "value": "cookie"},
        {"name": "token", "value": "abc"},
        {"name": None, "value": "ignored"},
        {"name": "missing", "value": None},
    ]
    driver = FakeDriver(cookies=cookies)

    result = my_events._fetch_cookies_via_selenium(
        "env-token",
        webdriver_factory=lambda: driver,
    )

    assert result == {"session": "cookie", "token": "abc"}
    assert driver.calls == [
        ("get", "https://www.go-out.co/"),
        ("add_cookie", {"name": "token", "value": "env-token"}),
        (
            "execute_script",
            "window.localStorage.setItem(arguments[0], arguments[1]);",
            my_events.LOCAL_STORAGE_TOKEN_KEY,
            "env-token",
        ),
        ("refresh", None),
        ("get_cookies", None),
        ("quit", None),
    ]


def test_ensure_auth_payload_initializes_missing_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    payload_dir = tmp_path / "payload"
    token_file = payload_dir / "token.txt"
    cookies_file = payload_dir / "cookies.json"

    monkeypatch.setattr(my_events, "PAYLOAD_DIR", payload_dir)
    monkeypatch.setattr(my_events, "TOKEN_FILE", token_file)
    monkeypatch.setattr(my_events, "COOKIES_FILE", cookies_file)

    captured: Dict[str, Any] = {}

    def fake_fetch(token: str, *, webdriver_factory=None):
        captured["token"] = token
        captured["factory_passed"] = webdriver_factory
        return {"session": "cookie"}

    monkeypatch.setattr(my_events, "_fetch_cookies_via_selenium", fake_fetch)
    monkeypatch.setenv(my_events.GOOUT_TOKEN_ENV, "from-env")

    my_events._ensure_auth_payload_initialized()

    assert payload_dir.exists()
    assert token_file.read_text(encoding="utf-8") == "from-env"
    assert json.loads(cookies_file.read_text(encoding="utf-8")) == {"session": "cookie"}
    assert captured == {"token": "from-env", "factory_passed": None}


def test_ensure_auth_payload_noop_when_files_exist(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    payload_dir = tmp_path / "payload"
    payload_dir.mkdir()
    token_file = payload_dir / "token.txt"
    cookies_file = payload_dir / "cookies.json"
    token_file.write_text("existing-token", encoding="utf-8")
    cookies_file.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(my_events, "PAYLOAD_DIR", payload_dir)
    monkeypatch.setattr(my_events, "TOKEN_FILE", token_file)
    monkeypatch.setattr(my_events, "COOKIES_FILE", cookies_file)

    called = False

    def fake_fetch(token: str, *, webdriver_factory=None):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(my_events, "_fetch_cookies_via_selenium", fake_fetch)
    monkeypatch.setenv(my_events.GOOUT_TOKEN_ENV, "should-not-use")

    my_events._ensure_auth_payload_initialized()

    assert not called
    assert token_file.read_text(encoding="utf-8") == "existing-token"
    assert cookies_file.read_text(encoding="utf-8") == "{}"
