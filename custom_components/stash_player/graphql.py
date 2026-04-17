"""GraphQL client for Stash."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse, urlunparse

import aiohttp
from homeassistant.exceptions import ConfigEntryAuthFailed


class StashConnectionError(Exception):
    """Raised for connectivity issues."""


class StashGraphQLError(Exception):
    """Raised for non-auth GraphQL issues."""


class StashInvalidURLError(Exception):
    """Raised when the configured Stash URL is not valid."""


def normalize_stash_url(raw_url: str) -> str:
    """Normalize user-entered Stash URL to base URL without /graphql suffix."""
    url = (raw_url or "").strip()
    if not url:
        raise StashInvalidURLError("URL is empty")
    if "://" not in url:
        url = f"http://{url}"
    url = url.rstrip("/")
    if url.endswith("/graphql"):
        url = url[: -len("/graphql")]
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise StashInvalidURLError("URL must use http or https with a valid host")
    return urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))


class StashGraphQLClient:
    """Async GraphQL client for Stash API."""

    def __init__(self, session: aiohttp.ClientSession, stash_url: str, api_key: str = "") -> None:
        self._session = session
        self._stash_url = stash_url.rstrip("/")
        self._api_key = api_key.strip()
        self._endpoint = f"{self._stash_url}/graphql"
        self._debug_logging = debug_logging

    @property
    def stash_url(self) -> str:
        return self._stash_url

    async def _post(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a GraphQL query/mutation, return the inner data dict."""
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables
        headers = {"ApiKey": self._api_key} if self._api_key else {}
        try:
            async with self._session.post(
                self._endpoint,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status in (401, 403):
                    raise ConfigEntryAuthFailed("Invalid API key")
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        except aiohttp.InvalidURL as err:
            raise StashInvalidURLError("Invalid Stash URL") from err
        except aiohttp.ClientError as err:
            raise StashConnectionError(str(err)) from err

        if errors := data.get("errors"):
            msg = errors[0].get("message", "Unknown GraphQL error")
            if "auth" in msg.lower() or "permission" in msg.lower():
                raise ConfigEntryAuthFailed(msg)
            raise StashGraphQLError(msg)

        return data.get("data", {})

    async def _post_allow_errors(self, query: str) -> dict[str, Any]:
        """Execute query and return raw JSON even when GraphQL errors are present."""
        payload = {"query": query}
        headers = {"ApiKey": self._api_key} if self._api_key else {}
        try:
            async with self._session.post(
                self._endpoint,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                resp.raise_for_status()
                return await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise StashConnectionError(str(err)) from err

    # ── Connection ─────────────────────────────────────────────────────────────

    async def validate_connection(self) -> None:
        """Test connectivity and auth with a lightweight query."""
        await self._post("query { version { version } }")

    # ── Media player queries ───────────────────────────────────────────────────

    async def query(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a query/mutation (used by media_player)."""
        return await self._post(query, variables)

    # ── Library stats ──────────────────────────────────────────────────────────

    async def async_get_scenes_count(self) -> int:
        data = await self._post("query { findScenes { count } }")
        return int(data["findScenes"]["count"])

    async def async_get_movies_count(self) -> int:
        """Return movie/group count, supporting both old and new Stash schemas."""
        raw = await self._post_allow_errors("query { findGroups { count } }")
        try:
            return int(raw["data"]["findGroups"]["count"])
        except (KeyError, TypeError, ValueError):
            pass
        raw2 = await self._post_allow_errors("query { findMovies { count } }")
        try:
            return int(raw2["data"]["findMovies"]["count"])
        except (KeyError, TypeError, ValueError) as err:
            raise StashGraphQLError(f"Cannot read movies/groups count: {raw2}") from err

    async def async_get_performers_count(self) -> int:
        data = await self._post("query { findPerformers { count } }")
        return int(data["findPerformers"]["count"])

    async def async_get_studios_count(self) -> int:
        data = await self._post("query { findStudios { count } }")
        return int(data["findStudios"]["count"])

    async def async_get_tags_count(self) -> int:
        data = await self._post("query { findTags { count } }")
        return int(data["findTags"]["count"])

    async def async_get_images_count(self) -> int:
        data = await self._post("query { findImages { count } }")
        return int(data["findImages"]["count"])

    async def async_get_galleries_count(self) -> int:
        data = await self._post("query { findGalleries { count } }")
        return int(data["findGalleries"]["count"])

    async def async_get_markers_count(self) -> int:
        data = await self._post("query { findSceneMarkers { count } }")
        return int(data["findSceneMarkers"]["count"])

    async def async_get_version(self) -> str | None:
        data = await self._post("query { version { version } }")
        try:
            return str(data["version"]["version"])
        except (KeyError, TypeError):
            return None

    # ── Admin mutations ────────────────────────────────────────────────────────

    async def async_metadata_scan(self) -> None:
        await self._post("mutation { metadataScan(input:{}) }")

    async def async_metadata_clean(self) -> None:
        await self._post('mutation { metadataClean(input: {dryRun: false, paths: ""}) }')

    async def async_metadata_generate(self) -> None:
        await self._post("mutation { metadataGenerate(input: {}) }")

    async def async_metadata_auto_tag(self) -> None:
        await self._post("mutation { metadataAutoTag(input: {}) }")

    async def async_metadata_identify(self) -> None:
        await self._post(
            'mutation { metadataIdentify(input: { sources: [{ source: { stash_box_endpoint: "https://stashdb.org/graphql" } }] }) }'
        )
