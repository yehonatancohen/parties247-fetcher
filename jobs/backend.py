"""Client for the Parties247 admin backend."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence
from urllib import parse as urllib_parse

import requests

LOGGER = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://parties247-backend.onrender.com"
LOGIN_ENDPOINT = "/api/admin/login"
IMPORT_ENDPOINT = "/api/admin/import/carousel-urls"
PASSWORD_ENV_VAR = "PARTIES247_ADMIN_PASSWORD"
DEFAULT_ENV_PATH = Path(".env")


class BackendError(RuntimeError):
    """Raised when the backend returns an error response."""


class BackendAuthenticationError(BackendError):
    """Raised when backend authentication fails."""


def _load_env(path: Path) -> Dict[str, str]:
    content = path.read_text(encoding="utf-8")
    values: Dict[str, str] = {}
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def get_admin_password(env_path: Optional[Path] = None) -> str:
    """Return the admin password from environment variables or a ``.env`` file."""

    password = os.environ.get(PASSWORD_ENV_VAR)
    if password:
        return password

    env_path = env_path or DEFAULT_ENV_PATH
    if not env_path.exists():
        raise BackendAuthenticationError(
            "Admin password not found in environment and .env file is missing"
        )

    values = _load_env(env_path)
    password = values.get(PASSWORD_ENV_VAR)
    if not password:
        raise BackendAuthenticationError(
            f"Admin password not found in {env_path}"
        )
    return password


class PartiesAdminClient:
    """Minimal client for interacting with the Parties247 admin backend."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        session: Optional[requests.Session] = None,
        env_path: Optional[Path] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._session = session or requests.Session()
        self._env_path = env_path
        self._token: Optional[str] = None

    def _url(self, path: str) -> str:
        return urllib_parse.urljoin(f"{self._base_url}/", path.lstrip("/"))

    def login(self) -> str:
        password = get_admin_password(env_path=self._env_path)
        response = self._session.post(
            self._url(LOGIN_ENDPOINT),
            json={"password": password},
            timeout=20,
        )
        if response.status_code == 401:
            raise BackendAuthenticationError("Invalid admin password")
        response.raise_for_status()
        data = response.json()
        token = data.get("token") if isinstance(data, Mapping) else None
        if not token:
            raise BackendAuthenticationError("Backend authentication response missing token")
        self._token = str(token)
        LOGGER.debug("Authenticated with Parties247 backend")
        return self._token

    def _authorization_header(self) -> Mapping[str, str]:
        if not self._token:
            self.login()
        return {"Authorization": f"Bearer {self._token}"}

    def import_carousel_urls(
        self,
        *,
        carousel_name: str,
        referral: Optional[str],
        urls: Sequence[str],
    ) -> Dict[str, object]:
        if not carousel_name:
            raise ValueError("carousel_name must be provided")

        headers = dict(self._authorization_header())
        payload = {
            "carouselName": carousel_name,
            "referral": referral,
            "urls": list(urls),
        }
        response = self._session.post(
            self._url(IMPORT_ENDPOINT),
            json=payload,
            headers=headers,
            timeout=20,
        )
        if response.status_code == 401:
            LOGGER.info("Backend token expired, attempting to re-authenticate")
            self._token = None
            headers = dict(self._authorization_header())
            response = self._session.post(
                self._url(IMPORT_ENDPOINT),
                json=payload,
                headers=headers,
                timeout=20,
            )
        response.raise_for_status()
        try:
            return response.json()
        except json.JSONDecodeError as exc:  # pragma: no cover - unexpected backend issue
            raise BackendError("Backend response was not valid JSON") from exc


__all__ = [
    "BackendAuthenticationError",
    "BackendError",
    "PartiesAdminClient",
    "get_admin_password",
]
