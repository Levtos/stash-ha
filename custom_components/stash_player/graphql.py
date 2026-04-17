"""GraphQL client for Stash."""

from __future__ import annotations

from typing import Any

import aiohttp
from homeassistant.exceptions import ConfigEntryAuthFailed


class StashConnectionError(Exception):
    """Raised for connectivity issues."""


class StashGraphQLError(Exception):
    """Raised for non-auth GraphQL issues."""


class StashGraphQLClient:
    """Simple GraphQL client for Stash API."""

    def __init__(self, session: aiohttp.ClientSession, stash_url: str, api_key: str) -> None:
        self._session = session
        self._stash_url = stash_url.rstrip("/")
        self._api_key = api_key
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
