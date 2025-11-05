from __future__ import annotations

import json
from pathlib import Path
from typing import List

import pytest

from jobs import my_events, nightlife, weekend
from jobs.go_out import GO_OUT_EVENT_BASE_URL


class DummyFetcher:
    def __init__(self, urls: List[str]) -> None:
        self._urls = urls

    def fetch_nightlife_events(self) -> List[str]:
        return self._urls

    def fetch_weekend_events(self) -> List[str]:
        return self._urls


def test_nightlife_run_job_returns_records(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    urls = ["https://example.com/event/a"]

    def fake_fetcher(*, referral=None):
        assert referral == "ref"
        return DummyFetcher(urls)

    monkeypatch.setattr(nightlife, "GoOutFetcher", fake_fetcher)
    output_file = tmp_path / "nightlife.json"

    records = nightlife.run_job(referral="ref", output_file=output_file)

    assert records == [{"title": "nightlife", "url": urls[0]}]
    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["events"] == records
    assert payload["count"] == 1


def test_weekend_run_job_returns_records(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    urls = ["https://example.com/event/weekend"]

    def fake_fetcher(*, referral=None):
        assert referral == "ref"
        return DummyFetcher(urls)

    monkeypatch.setattr(weekend, "GoOutFetcher", fake_fetcher)
    output_file = tmp_path / "weekend.json"

    records = weekend.run_job(referral="ref", output_file=output_file)

    assert records == [{"title": "weekend", "url": urls[0]}]
    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["events"] == records
    assert payload["count"] == 1


def test_my_events_run_job_extracts_urls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = {
        "events": [
            {"Url": "first"},
            {"slug": "second"},
        ]
    }

    monkeypatch.setattr(my_events, "fetch_events", lambda session=None: data)

    class FakeSession:
        pass

    monkeypatch.setattr(my_events.requests, "Session", lambda: FakeSession())

    output_file = tmp_path / "my_events.json"
    records = my_events.run_job(output_file=output_file)

    assert records == [
        {"title": "my_events", "url": f"{GO_OUT_EVENT_BASE_URL}first"},
        {"title": "my_events", "url": f"{GO_OUT_EVENT_BASE_URL}second"},
    ]
    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["events"] == records
    assert payload["raw"] == data
