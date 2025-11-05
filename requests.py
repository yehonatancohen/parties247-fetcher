"""Lightweight subset of the :mod:`requests` API used for offline testing."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

__all__ = [
    "RequestException",
    "Session",
    "Response",
    "get",
    "post",
]


class RequestException(Exception):
    """Base exception for HTTP errors."""


class HTTPError(RequestException):
    """Raised when the server returns an HTTP error status."""


@dataclass
class Response:
    status_code: int
    headers: Mapping[str, str]
    content: bytes
    url: str
    _error: Optional[HTTPError] = None

    def json(self) -> Any:
        return json.loads(self.text)

    @property
    def text(self) -> str:
        encoding = "utf-8"
        content_type = self.headers.get("Content-Type", "") if self.headers else ""
        if "charset=" in content_type:
            encoding = content_type.split("charset=")[-1].split(";", 1)[0].strip() or "utf-8"
        return self.content.decode(encoding, errors="replace")

    def raise_for_status(self) -> None:
        if self._error is not None:
            raise self._error


class Session:
    def request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        json: Optional[Any] = None,
        headers: Optional[Mapping[str, str]] = None,
        timeout: Optional[float] = None,
        proxies: Optional[Mapping[str, str]] = None,
    ) -> Response:
        if params:
            parsed = list(urllib_parse.urlparse(url))
            query = dict(urllib_parse.parse_qsl(parsed[4]))
            for key, value in params.items():
                if value is None:
                    continue
                query[str(key)] = str(value)
            parsed[4] = urllib_parse.urlencode(query)
            url = urllib_parse.urlunparse(parsed)

        data_bytes = None
        request_headers: Dict[str, str] = {}
        if headers:
            request_headers.update({str(k): str(v) for k, v in headers.items()})

        if json is not None:
            data_bytes = json_dump(json)
            request_headers.setdefault("Content-Type", "application/json")

        req = urllib_request.Request(url=url, data=data_bytes, method=method.upper())
        for key, value in request_headers.items():
            req.add_header(key, value)

        try:
            with urllib_request.urlopen(req, timeout=timeout) as response:
                content = response.read()
                headers_map = dict(response.headers.items()) if response.headers else {}
                return Response(
                    status_code=response.getcode() or 0,
                    headers=headers_map,
                    content=content,
                    url=response.geturl(),
                )
        except urllib_error.HTTPError as exc:
            content = exc.read() if hasattr(exc, "read") else b""
            headers_map = dict(exc.headers.items()) if exc.headers else {}
            error = HTTPError(str(exc))
            return Response(
                status_code=getattr(exc, "code", 0) or 0,
                headers=headers_map,
                content=content,
                url=url,
                _error=error,
            )
        except urllib_error.URLError as exc:  # pragma: no cover - network error handling
            raise RequestException(str(exc)) from exc

    def get(self, url: str, **kwargs: Any) -> Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> Response:
        return self.request("POST", url, **kwargs)


def get(url: str, **kwargs: Any) -> Response:  # pragma: no cover - simple passthrough
    return Session().get(url, **kwargs)


def post(url: str, **kwargs: Any) -> Response:  # pragma: no cover - simple passthrough
    return Session().post(url, **kwargs)


def json_dump(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")
