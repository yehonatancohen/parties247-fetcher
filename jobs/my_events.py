"""Fetch authenticated "my events" data from Go Out."""
from __future__ import annotations

import json
import logging
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests

from jobs.event_records import EventRecord, build_event_records
from jobs.go_out import _collect_go_out_event_urls

LOGGER = logging.getLogger(__name__)

PAYLOAD_DIR = Path("auth_payload")
TOKEN_FILE = PAYLOAD_DIR / "token.txt"
COOKIES_FILE = PAYLOAD_DIR / "cookies.json"
OUTPUT_FILE = Path("events.json")
LOGIN_URL = "https://api.fe.prod.go-out.co/auth/login"
EVENTS_URL = "https://api.fe.prod.go-out.co/events/myEvents"


class AuthenticationError(RuntimeError):
    """Raised when credentials are missing or invalid."""


def _get_env_creds() -> tuple[str, str]:
    email = os.environ.get("GOOUT_EMAIL")
    password = os.environ.get("GOOUT_PASSWORD")
    if not email or not password:
        raise AuthenticationError("GOOUT_EMAIL and GOOUT_PASSWORD must be set")
    return email, password


def _read_token() -> str:
    try:
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:  # pragma: no cover - configuration issue
        raise AuthenticationError("Authentication token file is missing") from exc


def _read_cookies() -> Dict[str, str]:
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
    TOKEN_FILE.write_text(token, encoding="utf-8")
    try:
        TOKEN_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:  # pragma: no cover - permissions vary
        LOGGER.debug("Unable to set permissions on %%s", TOKEN_FILE)
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
        cookies=_read_cookies(),
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


def save_events(
    data: Dict[str, object],
    records: List[EventRecord],
    output_file: Path = OUTPUT_FILE,
) -> None:
    payload = {
        "retrieved_at": datetime.now(tz=timezone.utc).isoformat(),
        "count": len(records),
        "events": records,
        "raw": data,
    }
    output_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _extract_event_records(data: Dict[str, object]) -> List[EventRecord]:
    """Extract affiliate-ready URLs from ``my events`` API payloads."""

    events = []
    if isinstance(data, dict):
        raw_events = data.get("events")
        if isinstance(raw_events, list):
            events = raw_events
    urls = _collect_go_out_event_urls(events, referral=None)
    return build_event_records("my_events", urls)


def run_job(output_file: Path = OUTPUT_FILE) -> List[EventRecord]:
    session = requests.Session()
    data = fetch_events(session=session)
    records = _extract_event_records(data)
    save_events(data, records, output_file=output_file)
    LOGGER.info("Fetched %%d 'my events' URLs", len(records))
    return records


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    run_job()
