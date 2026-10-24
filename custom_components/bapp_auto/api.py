"""Thin async client for the bapp generic API, as used by the bapp-auto app."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import aiohttp
from yarl import URL

from .const import APP_SLUG, MAX_PAGES, REQUEST_TIMEOUT

_LOGGER = logging.getLogger(__name__)

# Returns the value of the Authorization header, refreshing credentials if needed.
type AuthProvider = Callable[[], Awaitable[str]]


class BappAutoError(Exception):
    """Base error."""


class BappAutoAuthError(BappAutoError):
    """The credentials were rejected."""


class BappAutoConnectionError(BappAutoError):
    """The server could not be reached."""


class BappAutoClient:
    """Calls the generic content-type and task endpoints with a bearer token."""

    def __init__(self, session: aiohttp.ClientSession, host: str, auth: AuthProvider) -> None:
        self._session = session
        self.host = host.rstrip("/")
        self._api = URL(self.host) / "api"
        self._auth = auth

    async def _headers(self) -> dict[str, str]:
        try:
            authorization = await self._auth()
        except aiohttp.ClientResponseError as err:
            if err.status in (400, 401, 403):
                raise BappAutoAuthError(f"Token refresh rejected: HTTP {err.status}") from err
            raise BappAutoConnectionError(f"Token refresh failed: {err}") from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise BappAutoConnectionError(f"Token refresh failed: {err}") from err
        return {"Authorization": authorization, "X-App-Slug": APP_SLUG, "Accept": "application/json"}

    async def _request(self, method: str, url: URL, **kwargs: Any) -> Any:
        headers = await self._headers()
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                response = await self._session.request(method, url, headers=headers, **kwargs)
                if response.status in (401, 403, 498):
                    raise BappAutoAuthError(f"HTTP {response.status} for {url.path}")
                if response.status >= 400:
                    text = await response.text()
                    raise BappAutoError(f"HTTP {response.status} for {url.path}: {text[:200]}")
                return await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise BappAutoConnectionError(f"{method} {url.path}: {err}") from err

    def _content_type_url(self, content_type: str) -> URL:
        return self._api / "content-type" / content_type / ""

    async def async_validate(self) -> None:
        """Raise if the credentials cannot list the account's cars."""
        await self._request("GET", self._content_type_url("bapp_auto.car").with_query(page_size=1))

    async def async_list(self, content_type: str, **params: Any) -> list[dict[str, Any]]:
        """Fetch every page of a content-type list."""
        url = self._content_type_url(content_type)
        results: list[dict[str, Any]] = []
        next_url: URL | None = url.with_query({"page_size": 100, **params})
        pages = 0
        while next_url is not None and pages < MAX_PAGES:
            data = await self._request("GET", next_url)
            pages += 1
            if isinstance(data, list):
                results.extend(data)
                break
            results.extend(data.get("results") or [])
            # Rebuild from our own base: the server's `next` carries its internal host.
            next_url = url.with_query(URL(next_link).query) if (next_link := data.get("next")) else None
        return results

    async def async_run_task(self, code: str, payload: dict[str, Any]) -> dict[str, Any]:
        """POST a DirectTask and return its response dict ({success, message, data})."""
        data = await self._request("POST", self._api / "tasks" / code, json=payload)
        if not isinstance(data, dict):
            raise BappAutoError(f"Unexpected task response for {code}: {data!r}")
        return data

    async def async_fetch_bytes(self, url: str) -> tuple[bytes, str | None]:
        """Download a media file. Credentials go only to our own host."""
        target = URL(url)
        headers = await self._headers() if target.host == self._api.host else {}
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                response = await self._session.get(target, headers=headers)
                if response.status >= 400:
                    raise BappAutoError(f"HTTP {response.status} fetching {target.path}")
                return await response.read(), response.headers.get("Content-Type")
        except (aiohttp.ClientError, TimeoutError) as err:
            raise BappAutoConnectionError(f"GET {target.path}: {err}") from err
