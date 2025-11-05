from __future__ import annotations

from typing import Any, Dict, Optional

from jobs.go_out import (
    GO_OUT_EVENT_BASE_URL,
    GoOutFetcher,
    append_affiliate_param,
    _collect_go_out_event_urls,
    _extract_event_slug_from_ticket_item,
)


class MockResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        json_data: Optional[Dict[str, Any]] = None,
        text: str = "",
        json_error: Optional[Exception] = None,
    ) -> None:
        self.status_code = status_code
        self._json_data = json_data
        self.text = text
        self._json_error = json_error

    def json(self) -> Dict[str, Any]:
        if self._json_error is not None:
            raise self._json_error
        if self._json_data is None:
            raise ValueError("No JSON data provided")
        return self._json_data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


class MockSession:
    def __init__(self, *, response: MockResponse, html_response: MockResponse) -> None:
        self._response = response
        self._html_response = html_response
        self.request_calls = []
        self.get_calls = []

    def request(self, *args: Any, **kwargs: Any) -> MockResponse:
        self.request_calls.append((args, kwargs))
        return self._response

    def get(self, *args: Any, **kwargs: Any) -> MockResponse:
        self.get_calls.append((args, kwargs))
        return self._html_response


def test_append_affiliate_param_overwrites_existing_affiliate() -> None:
    url = "https://example.com/event/foo?aff=old&b=2"
    updated = append_affiliate_param(url, "new")
    assert updated.endswith("aff=new&b=2") or updated.endswith("b=2&aff=new")


def test_collect_go_out_event_urls_deduplicates_and_formats() -> None:
    events = [
        {"Url": "foo-party"},
        {"url": "https://www.go-out.co/event/bar-bash"},
        {"Url": "foo-party"},  # duplicate
    ]
    urls = _collect_go_out_event_urls(events, "ref")
    assert urls == [
        append_affiliate_param(f"{GO_OUT_EVENT_BASE_URL}foo-party", "ref"),
        append_affiliate_param(f"{GO_OUT_EVENT_BASE_URL}bar-bash", "ref"),
    ]


def test_extract_event_slug_handles_numeric() -> None:
    item = {"id": 12345}
    assert _extract_event_slug_from_ticket_item(item) == "12345"


def test_fetcher_prefers_api_data() -> None:
    response = MockResponse(json_data={"events": [{"Url": "foo"}]})
    html_response = MockResponse(text="<a href='/event/html-fallback'></a>")
    session = MockSession(response=response, html_response=html_response)
    fetcher = GoOutFetcher(referral="abc", session=session)

    urls = fetcher.fetch_nightlife_events()

    assert urls == [append_affiliate_param(f"{GO_OUT_EVENT_BASE_URL}foo", "abc")]
    assert len(session.request_calls) == 1
    assert len(session.get_calls) == 0


def test_fetcher_uses_html_fallback_on_json_error() -> None:
    response = MockResponse(json_error=ValueError("no json"))
    html_response = MockResponse(text="<a href='/event/from-html'></a>")
    session = MockSession(response=response, html_response=html_response)
    fetcher = GoOutFetcher(referral=None, session=session)

    urls = fetcher.fetch_weekend_events()

    assert urls == [f"{GO_OUT_EVENT_BASE_URL}from-html"]
    assert len(session.request_calls) == 1
    assert len(session.get_calls) == 1
