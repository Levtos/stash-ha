"""GraphQL client for Stash."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit, urlunsplit
import logging

import aiohttp
from homeassistant.exceptions import ConfigEntryAuthFailed

_LOGGER = logging.getLogger(__name__)


class StashConnectionError(Exception):
    """Raised for connectivity issues."""


class StashGraphQLError(Exception):
    """Raised for non-auth GraphQL issues."""


class StashInvalidURLError(Exception):
    """Raised when the configured Stash URL is not valid."""


def normalize_stash_url(raw_url: str) -> str:
    """Normalize user-entered Stash URL.

    Accept host-only values like ``192.168.178.113`` and auto-prefix
    ``http://`` when no scheme is provided.
    """
    url = (raw_url or "").strip()
    if not url:
        raise StashInvalidURLError("URL is empty")

    if "://" not in url:
        url = f"http://{url}"

    try:
        parsed = urlsplit(url)
    except ValueError as err:
        raise StashInvalidURLError("Invalid URL") from err

    if parsed.scheme not in ("http", "https"):
        raise StashInvalidURLError("URL must start with http:// or https://")

    if not parsed.hostname:
        raise StashInvalidURLError("URL must include a valid host")

    cleaned = urlunsplit((parsed.scheme, parsed.netloc, "", "", "")).rstrip("/")
    return cleaned


class StashGraphQLClient:
    """Simple GraphQL client for Stash API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        stash_url: str,
        api_key: str,
        debug_logging: bool = False,
    ) -> None:
        self._session = session
        self._stash_url = normalize_stash_url(stash_url)
        self._api_key = api_key.strip()
        self._endpoint = f"{self._stash_url}/graphql"
        self._debug_logging = debug_logging

    @property
    def stash_url(self) -> str:
        """Return normalized stash URL."""
        return self._stash_url

    @property
    def endpoint(self) -> str:
        """Return the currently active GraphQL endpoint."""
        return self._endpoint

    def _endpoint_candidates(self) -> list[str]:
        """Return endpoint candidates for compatibility with different deployments."""
        candidates = [self._endpoint]
        if self._endpoint.endswith("/graphql"):
            candidates.append(f"{self._stash_url}/api/graphql")
        return list(dict.fromkeys(candidates))

    def _headers(self) -> dict[str, str]:
        """Return request headers for GraphQL calls."""
        if self._api_key:
            return {"ApiKey": self._api_key}
        return {}

    async def query(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute GraphQL query."""
        payload: dict[str, Any] = {"query": query.strip()}
        if variables:
            payload["variables"] = variables

        if self._debug_logging:
            _LOGGER.debug("Stash GraphQL request (has_variables=%s)", bool(variables))

        last_http_error: str | None = None

        for endpoint in self._endpoint_candidates():
            try:
                async with self._session.post(
                    endpoint,
                    json=payload,
                    headers=self._headers(),
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    raw_body = await response.text()

                    if response.status in (401, 403):
                        _LOGGER.warning("Stash auth failed for %s (status=%s)", endpoint, response.status)
                        raise ConfigEntryAuthFailed("Invalid API key")

                    if response.status >= 400:
                        last_http_error = f"HTTP {response.status}: {raw_body[:200]}"
                        _LOGGER.error(
                            "Stash HTTP error %s on %s. Response body: %s",
                            response.status,
                            endpoint,
                            raw_body[:500],
                        )
                        continue

                    data = await response.json(content_type=None)
                    if endpoint != self._endpoint:
                        _LOGGER.info("stash_player switched GraphQL endpoint from %s to %s", self._endpoint, endpoint)
                        self._endpoint = endpoint
                    break
            except aiohttp.InvalidURL as err:
                _LOGGER.error("Invalid Stash URL: %s", endpoint)
                raise StashInvalidURLError("Invalid Stash URL") from err
            except aiohttp.ClientError as err:
                _LOGGER.error("Could not reach Stash at %s: %s", endpoint, err)
                last_http_error = str(err)
                continue
        else:
            if last_http_error:
                raise StashGraphQLError(last_http_error)
            raise StashConnectionError("Unable to reach Stash")

        if errors := data.get("errors"):
            message = errors[0].get("message", "Unknown GraphQL error")
            _LOGGER.warning("Stash GraphQL returned error: %s", message)
            if "auth" in message.lower() or "permission" in message.lower():
                raise ConfigEntryAuthFailed(message)
            raise StashGraphQLError(message)

        return data.get("data", {})

    async def validate_connection(self) -> None:
        """Validate credentials and connectivity with compatibility fallback."""
        try:
            await self.query("query Health { version { version } }")
        except StashGraphQLError:
            await self.query("query Health { __typename }")
