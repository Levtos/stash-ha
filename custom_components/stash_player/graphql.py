"""GraphQL client for Stash."""

from __future__ import annotations

from typing import Any

import aiohttp
from homeassistant.exceptions import ConfigEntryAuthFailed


class StashConnectionError(Exception):
    """Raised for connectivity issues."""


class StashGraphQLError(Exception):
    """Raised for non-auth GraphQL issues."""


class StashInvalidURLError(Exception):
    """Raised when the configured Stash URL is not valid."""


def normalize_stash_url(raw_url: str) -> str:
    """Normalize user-entered Stash URL.

    Accepts host-only values like `192.168.178.113` and automatically prefixes
    `http://` when no scheme is provided.
    """
    url = (raw_url or "").strip()
    if not url:
        raise StashInvalidURLError("URL is empty")

    if "://" not in url:
        url = f"http://{url}"

    parsed = aiohttp.client_reqrep.URL(url)
    if parsed.scheme not in ("http", "https") or not parsed.host:
        raise StashInvalidURLError("URL must include a valid host and http/https scheme")

    return str(parsed.with_path("").with_query(None).with_fragment(None)).rstrip("/")


class StashGraphQLClient:
    """Simple GraphQL client for Stash API."""

    def __init__(self, session: aiohttp.ClientSession, stash_url: str, api_key: str) -> None:
        self._session = session
        self._stash_url = normalize_stash_url(stash_url)
        self._api_key = api_key.strip()
        self._endpoint = f"{self._stash_url}/graphql"

    @property
    def stash_url(self) -> str:
        """Return normalized stash URL."""
        return self._stash_url

    async def query(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute GraphQL query."""
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            async with self._session.post(
                self._endpoint,
                json=payload,
                headers={"ApiKey": self._api_key},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status in (401, 403):
                    raise ConfigEntryAuthFailed("Invalid API key")

                response.raise_for_status()
                data = await response.json(content_type=None)
        except aiohttp.InvalidURL as err:
            raise StashInvalidURLError("Invalid Stash URL") from err
        except aiohttp.ClientError as err:
            raise StashConnectionError("Unable to reach Stash") from err

        if errors := data.get("errors"):
            message = errors[0].get("message", "Unknown GraphQL error")
            if "auth" in message.lower() or "permission" in message.lower():
                raise ConfigEntryAuthFailed(message)
            raise StashGraphQLError(message)

        return data.get("data", {})

    async def validate_connection(self) -> None:
        """Validate credentials and connectivity with a lightweight query."""
        await self.query("query Ping { systemStatus { databaseSchema } }")
