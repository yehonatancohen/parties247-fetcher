"""Fetch authenticated "my events" data from Go Out."""
from __future__ import annotations

import json
import logging
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional

import requests

from jobs.backend import PartiesAdminClient
from jobs.event_records import EventRecord, build_event_records
from jobs.go_out import _collect_go_out_event_urls

LOGGER = logging.getLogger(__name__)

PAYLOAD_DIR = Path("auth_payload")
TOKEN_FILE = PAYLOAD_DIR / "token.txt"
COOKIES_FILE = PAYLOAD_DIR / "cookies.json"
LOCAL_STORAGE_TOKEN_KEY = "authToken"
GOOUT_TOKEN_ENV = "GOOUT_TOKEN"
LOGIN_URL = "https://api.fe.prod.go-out.co/auth/login"
EVENTS_URL = "https://api.fe.prod.go-out.co/events/myEvents"
CAROUSEL_NAME = "my_events"


class AuthenticationError(RuntimeError):
    """Raised when credentials are missing or invalid."""


def _get_env_creds() -> tuple[str, str]:
    email = os.environ.get("GOOUT_EMAIL")
    password = os.environ.get("GOOUT_PASSWORD")
    if not email or not password:
        raise AuthenticationError("GOOUT_EMAIL and GOOUT_PASSWORD must be set")
    return email, password


def _get_env_token() -> str:
    token = os.environ.get(GOOUT_TOKEN_ENV)
    if not token:
        raise AuthenticationError(f"{GOOUT_TOKEN_ENV} must be set to bootstrap authentication")
    return token


def _write_token_file(token: str) -> None:
    TOKEN_FILE.write_text(token, encoding="utf-8")
    try:
        TOKEN_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:  # pragma: no cover - permissions vary by platform
        LOGGER.debug("Unable to set permissions on %s", TOKEN_FILE)


def _write_cookies_file(cookies: Mapping[str, str]) -> None:
    with COOKIES_FILE.open("w", encoding="utf-8") as file:
        json.dump(dict(cookies), file, ensure_ascii=False, indent=2)
    try:
        COOKIES_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:  # pragma: no cover - permissions vary by platform
        LOGGER.debug("Unable to set permissions on %s", COOKIES_FILE)


def _create_webdriver() -> Any:
    try:
        from selenium import webdriver
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise AuthenticationError("Selenium is required to bootstrap Go Out authentication") from exc

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=options)


def _fetch_cookies_via_selenium(
    token: str,
    *,
    webdriver_factory: Optional[Callable[[], Any]] = None,
) -> Dict[str, str]:
    factory = webdriver_factory or _create_webdriver
    driver = factory()
    try:
        driver.get("https://www.go-out.co/")
        try:
            driver.add_cookie({"name": "token", "value": token})
        except Exception:  # pragma: no cover - browser specific behaviour
            LOGGER.debug("Unable to persist token as cookie via Selenium")
        try:
            driver.execute_script(
                "window.localStorage.setItem(arguments[0], arguments[1]);",
                LOCAL_STORAGE_TOKEN_KEY,
                token,
            )
        except Exception:  # pragma: no cover - browser specific behaviour
            LOGGER.debug("Unable to persist token to localStorage via Selenium")
        try:
            driver.refresh()
        except Exception:  # pragma: no cover - browser specific behaviour
            LOGGER.debug("Unable to refresh Selenium page after authentication bootstrap")
        raw_cookies = driver.get_cookies() or []
    finally:
        try:
            driver.quit()
        except Exception:  # pragma: no cover - browser specific behaviour
            LOGGER.debug("Unable to gracefully quit Selenium webdriver")

    cookies: Dict[str, str] = {}
    for entry in raw_cookies:
        if not isinstance(entry, Mapping):
            continue
        name = entry.get("name")
        value = entry.get("value")
        if not name or value is None:
            continue
        cookies[str(name)] = str(value)
    return cookies


def _ensure_auth_payload_initialized(*, webdriver_factory: Optional[Callable[[], Any]] = None) -> None:
    if PAYLOAD_DIR.exists() and TOKEN_FILE.exists() and COOKIES_FILE.exists():
        return

    PAYLOAD_DIR.mkdir(parents=True, exist_ok=True)
    token = _get_env_token()
    _write_token_file(token)

    cookies = _fetch_cookies_via_selenium(token, webdriver_factory=webdriver_factory)
    if not cookies:
        LOGGER.warning("No cookies were retrieved via Selenium; authentication may fail")
    _write_cookies_file(cookies)


def _read_token() -> str:
    _ensure_auth_payload_initialized()
    try:
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:  # pragma: no cover - configuration issue
        raise AuthenticationError("Authentication token file is missing") from exc


def _read_cookies() -> Dict[str, str]:
    _ensure_auth_payload_initialized()
    try:
        with COOKIES_FILE.open(encoding="utf-8") as file:
            content = json.load(file)
        if not isinstance(content, dict):
            raise ValueError("Cookies file must contain a JSON object")
        return {str(k): str(v) for k, v in content.items()}
    except FileNotFoundError as exc:  # pragma: no cover - configuration issue
        raise AuthenticationError("Cookies file is missing") from exc


def renew_token_from_env(session: Optional[requests.Session] = None) -> str:
    email, password = _get_env_creds()
    payload = {"username": email, "password": password}
    session = session or requests.Session()
    response = session.post(LOGIN_URL, json=payload, timeout=20)
    if response.status_code != 200:
        raise AuthenticationError(
            f"Login failed: {response.status_code} {response.text[:200]}"
        )
    data = response.json()
    token = data.get("token") or data.get("access_token")
    if not token:
        raise AuthenticationError("No token provided in authentication response")
    PAYLOAD_DIR.mkdir(parents=True, exist_ok=True)
    _write_token_file(token)
    LOGGER.info("Renewed Go Out API token")
    return token


def fetch_events(session: Optional[requests.Session] = None) -> Dict[str, object]:
    session = session or requests.Session()
    headers = {
        "Authorization": f"Bearer {_read_token()}",
        "Accept": "application/json",
        "Origin": "https://www.go-out.co",
    }
    params = {
        "skip": 0,
        "limit": 100,
        "filter": '{"Title":"","activeEvents":true}',
        "currentDate": datetime.now(tz=timezone.utc).isoformat(),
    }
    response = session.get(
        EVENTS_URL,
        headers=headers,
        #cookies=_read_cookies(),
        params=params,
        timeout=20,
    )
    if response.status_code == 401:
        LOGGER.info("Token expired, attempting renewal")
        headers["Authorization"] = f"Bearer {renew_token_from_env(session)}"
        response = session.get(
            EVENTS_URL,
            headers=headers,
            cookies=_read_cookies(),
            params=params,
            timeout=20,
        )
    response.raise_for_status()
    return response.json()


def _extract_event_records(data: Dict[str, object]) -> List[EventRecord]:
    """Extract affiliate-ready URLs from ``my events`` API payloads."""

    events = []
    if isinstance(data, dict):
        raw_events = data.get("events")
        if isinstance(raw_events, list):
            events = raw_events
    urls = _collect_go_out_event_urls(events, referral=None)
    return build_event_records(CAROUSEL_NAME, urls)


def run_job(
    *,
    admin_client: Optional[PartiesAdminClient] = None,
    session: Optional[requests.Session] = None,
) -> List[EventRecord]:
    """Fetch "my events" data and upload event URLs to the backend."""

    session = session or requests.Session()
    data = fetch_events(session=session)
    records = _extract_event_records(data)

    client = admin_client or PartiesAdminClient()
    urls = [record["url"] for record in records]
    client.add_party_urls(urls=urls)
    LOGGER.info("Sent %d 'my events' URLs to backend", len(records))
    return records


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    run_job()
