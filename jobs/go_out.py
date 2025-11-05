"""Utilities for fetching events from the Go Out API."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, List, Mapping, MutableMapping, Optional
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import requests

LOGGER = logging.getLogger(__name__)

GO_OUT_BASE_URL = "https://www.go-out.co"
GO_OUT_API_BASE_URL = urljoin(GO_OUT_BASE_URL, "/endOne/")
GO_OUT_EVENT_BASE_URL = urljoin(GO_OUT_BASE_URL, "/event/")
DEFAULT_TIMEOUT = 15

DISABLE_PROXIES = {"http": None, "https": None}


def _format_iso_timestamp() -> str:
    """Return an ISO 8601 timestamp in UTC including timezone information."""
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()


def append_affiliate_param(url: str, referral: Optional[str]) -> str:
    """Append an affiliate parameter to *url* if *referral* is provided."""
    if not referral:
        return url
    parsed = urlparse(url)
    query = list(parse_qsl(parsed.query, keep_blank_values=True))
    query = [(k, v) for k, v in query if k != "aff"]
    query.append(("aff", referral))
    encoded = urlencode(query)
    return urlunparse(parsed._replace(query=encoded))


def _clean_slug(slug: str) -> Optional[str]:
    slug = slug.strip().lstrip("/")
    if not slug:
        return None
    if "/" in slug:
        slug = slug.rsplit("/", 1)[-1]
    return slug or None


def _extract_event_slug_from_ticket_item(item: Mapping[str, object]) -> Optional[str]:
    if not isinstance(item, Mapping):
        return None
    for key in ("Url", "url", "slug", "Slug", "_id", "id"):
        if key not in item:
            continue
        value = item.get(key)
        if value is None:
            continue
        if isinstance(value, (int, float)):
            value = str(int(value))
        text = str(value).strip()
        if not text:
            continue
        if "/" in text:
            parsed = urlparse(text)
            if parsed.path and "/event/" in parsed.path:
                slug = parsed.path.rsplit("/", 1)[-1]
                return _clean_slug(slug)
        return _clean_slug(text)
    return None


def _collect_go_out_event_urls(events: Iterable[Mapping[str, object]], referral: Optional[str]) -> List[str]:
    urls: List[str] = []
    seen: set[str] = set()
    for event in events or []:
        slug = _extract_event_slug_from_ticket_item(event)
        if not slug:
            continue
        event_url = f"{GO_OUT_EVENT_BASE_URL}{slug}"
        event_url = append_affiliate_param(event_url, referral)
        if event_url in seen:
            continue
        seen.add(event_url)
        urls.append(event_url)
    return urls


@dataclass
class GoOutFetcher:
    """A helper that fetches Go Out events with a graceful HTML fallback."""

    referral: Optional[str] = None
    session: requests.Session = field(default_factory=requests.Session)
    timeout: int = DEFAULT_TIMEOUT

    def fetch_nightlife_events(self) -> List[str]:
        payload: MutableMapping[str, object] = {
            "skip": 0,
            "limit": 50,
            "location": "IL",
            "Types": ["תל אביב", "מועדוני לילה"],
            "recivedDate": _format_iso_timestamp(),
        }
        endpoint = urljoin(GO_OUT_API_BASE_URL, "getEventsByTypeNew")
        return self._fetch_events(
            method="POST",
            url=endpoint,
            json_payload=payload,
            fallback_path="/tickets/nightlife",
        )

    def fetch_weekend_events(self) -> List[str]:
        params: MutableMapping[str, object] = {
            "limit": 50,
            "skip": 0,
            "recivedDate": _format_iso_timestamp(),
            "location": "IL",
        }
        endpoint = urljoin(GO_OUT_API_BASE_URL, "getWeekendEvents")
        return self._fetch_events(
            method="GET",
            url=endpoint,
            params=params,
            fallback_path="/weekend",
        )

    def _fetch_events(
        self,
        *,
        method: str,
        url: str,
        fallback_path: str,
        json_payload: Optional[Mapping[str, object]] = None,
        params: Optional[Mapping[str, object]] = None,
    ) -> List[str]:
        LOGGER.info("Fetching Go Out events from %%s", url)
        try:
            response = self.session.request(
                method=method,
                url=url,
                json=json_payload,
                params=params,
                timeout=self.timeout,
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                proxies=DISABLE_PROXIES,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:  # pragma: no cover - network error
            LOGGER.warning("Go Out API request failed, falling back to HTML: %%s", exc)
            return self._scrape_events_from_html(fallback_path)
        except (ValueError, json.JSONDecodeError):
            LOGGER.warning("Go Out API returned invalid JSON, falling back to HTML")
            return self._scrape_events_from_html(fallback_path)

        events = data.get("events") if isinstance(data, Mapping) else []
        if not events:
            LOGGER.info("No events returned from API, attempting HTML fallback")
            return self._scrape_events_from_html(fallback_path)
        urls = _collect_go_out_event_urls(events, self.referral)
        LOGGER.info("Collected %%d event URLs from API", len(urls))
        return urls

    def _scrape_events_from_html(self, path: str) -> List[str]:
        page_url = urljoin(GO_OUT_BASE_URL, path)
        LOGGER.info("Scraping Go Out events from %%s", page_url)
        try:
            response = self.session.get(
                page_url,
                timeout=self.timeout,
                headers={"User-Agent": "Mozilla/5.0"},
                proxies=DISABLE_PROXIES,
            )
            response.raise_for_status()
            html = response.text
        except requests.RequestException as exc:  # pragma: no cover - network error
            LOGGER.error("Failed to scrape Go Out HTML page: %%s", exc)
            return []

        slugs = _extract_slugs_from_html(html)
        urls = [append_affiliate_param(f"{GO_OUT_EVENT_BASE_URL}{slug}", self.referral) for slug in slugs]
        LOGGER.info("Collected %%d event URLs from HTML", len(urls))
        return urls


def _extract_slugs_from_html(html: str) -> List[str]:
    import re

    pattern = re.compile(r"/event/([a-zA-Z0-9-]+)")
    slugs: List[str] = []
    seen: set[str] = set()
    for match in pattern.finditer(html):
        slug = match.group(1)
        if slug in seen:
            continue
        seen.add(slug)
        slugs.append(slug)
    return slugs


__all__ = [
    "GoOutFetcher",
    "append_affiliate_param",
    "_collect_go_out_event_urls",
    "_extract_event_slug_from_ticket_item",
    "_extract_slugs_from_html",
]
