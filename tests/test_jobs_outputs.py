from __future__ import annotations

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


class DummyAdminClient:
    def __init__(self) -> None:
        self.calls = []

    def import_carousel_urls(self, *, carousel_name: str, referral, urls: List[str]):
        self.calls.append({
            "carousel_name": carousel_name,
            "referral": referral,
            "urls": list(urls),
        })
        return {"message": "ok"}


def test_nightlife_run_job_returns_records(monkeypatch: pytest.MonkeyPatch) -> None:
    urls = ["https://example.com/event/a"]

    def fake_fetcher(*, referral=None):
        assert referral == "ref"
        return DummyFetcher(urls)

    monkeypatch.setattr(nightlife, "GoOutFetcher", fake_fetcher)
    client = DummyAdminClient()

    records = nightlife.run_job(referral="ref", admin_client=client)

    assert records == [{"title": "nightlife", "url": urls[0]}]
    assert client.calls == [
        {
            "carousel_name": "nightlife",
            "referral": "ref",
            "urls": urls,
        }
    ]


def test_weekend_run_job_returns_records(monkeypatch: pytest.MonkeyPatch) -> None:
    urls = ["https://example.com/event/weekend"]

    def fake_fetcher(*, referral=None):
        assert referral == "ref"
        return DummyFetcher(urls)

    monkeypatch.setattr(weekend, "GoOutFetcher", fake_fetcher)
    client = DummyAdminClient()

    records = weekend.run_job(referral="ref", admin_client=client)

    assert records == [{"title": "weekend", "url": urls[0]}]
    assert client.calls == [
        {
            "carousel_name": "weekend",
            "referral": "ref",
            "urls": urls,
        }
    ]


def test_my_events_run_job_extracts_urls(monkeypatch: pytest.MonkeyPatch) -> None:
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
    client = DummyAdminClient()

    records = my_events.run_job(admin_client=client)

    assert records == [
        {"title": "my_events", "url": f"{GO_OUT_EVENT_BASE_URL}first"},
        {"title": "my_events", "url": f"{GO_OUT_EVENT_BASE_URL}second"},
    ]
    assert client.calls == [
        {
            "carousel_name": "my_events",
            "referral": None,
            "urls": [record["url"] for record in records],
        }
    ]
