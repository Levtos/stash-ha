"""Stash Player integration — based on Druidblack/stash-home-assistant."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
import re
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    ACTIVE_SCENE_QUERY,
    CLIENT_KEY,
    CONF_API_KEY,
    CONF_POLL_INTERVAL,
    CONF_URL,
    CONF_USE_WEBHOOK,
    COORDINATOR_KEY,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LIBRARY_COORDINATOR_KEY,
    PLATFORMS,
    PLAYING_STATE_QUERY,
    RECENT_STREAM_GRACE_SECONDS,
    SCENE_BY_ID_QUERY,
    WEBHOOK_VIEW_KEY,
)

_LOGGER = logging.getLogger(__name__)


class StashError(Exception):
    """Base error for Stash API."""


class StashClient:
    """Simple async GraphQL client for Stash."""

    def __init__(self, graphql_url: str, session, api_key: str = "") -> None:
        self._url = graphql_url.rstrip("/")
        self._session = session
        self._api_key = api_key.strip()
        self._base_url = self._url[:-len("/graphql")] if self._url.endswith("/graphql") else self._url

    @property
    def stash_url(self) -> str:
        return self._base_url

    def _headers(self) -> dict:
        return {"ApiKey": self._api_key} if self._api_key else {}

    async def _post(self, query: str, variables: dict | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables
        async with asyncio.timeout(10):
            async with self._session.post(self._url, json=payload, headers=self._headers()) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise StashError(f"HTTP {resp.status}: {text}")
                data = await resp.json()
        if "errors" in data:
            raise StashError(f"GraphQL errors: {data['errors']}")
        return data

    async def _post_allow_errors(self, query: str) -> dict[str, Any]:
        payload = {"query": query}
        async with asyncio.timeout(10):
            async with self._session.post(self._url, json=payload, headers=self._headers()) as resp:
                if resp.status != 200:
                    raise StashError(f"HTTP {resp.status}")
                return await resp.json()

    async def validate(self) -> None:
        await self._post("query { version { version } }")

    async def get_scenes_count(self) -> int:
        data = await self._post("query { findScenes { count } }")
        return int(data["data"]["findScenes"]["count"])

    async def get_movies_count(self) -> int:
        raw = await self._post_allow_errors("query { findGroups { count } }")
        try:
            return int(raw["data"]["findGroups"]["count"])
        except (KeyError, TypeError, ValueError):
            pass
        raw2 = await self._post_allow_errors("query { findMovies { count } }")
        try:
            return int(raw2["data"]["findMovies"]["count"])
        except (KeyError, TypeError, ValueError):
            return 0

    async def get_performers_count(self) -> int:
        data = await self._post("query { findPerformers { count } }")
        return int(data["data"]["findPerformers"]["count"])

    async def get_studios_count(self) -> int:
        data = await self._post("query { findStudios { count } }")
        return int(data["data"]["findStudios"]["count"])

    async def get_tags_count(self) -> int:
        data = await self._post("query { findTags { count } }")
        return int(data["data"]["findTags"]["count"])

    async def get_images_count(self) -> int:
        data = await self._post("query { findImages { count } }")
        return int(data["data"]["findImages"]["count"])

    async def get_galleries_count(self) -> int:
        data = await self._post("query { findGalleries { count } }")
        return int(data["data"]["findGalleries"]["count"])

    async def get_markers_count(self) -> int:
        data = await self._post("query { findSceneMarkers { count } }")
        return int(data["data"]["findSceneMarkers"]["count"])

    async def get_version(self) -> str | None:
        data = await self._post("query { version { version } }")
        try:
            return str(data["data"]["version"]["version"])
        except (KeyError, TypeError):
            return None

    async def generate_screenshot(self, scene_id: str) -> None:
        await self._post_allow_errors(
            f'mutation {{ sceneGenerateScreenshot(id: "{scene_id}") }}'
        )

    async def save_activity(self, scene_id: str, position: float) -> None:
        await self._post_allow_errors(
            f'mutation {{ sceneSaveActivity(id: "{scene_id}", resume_time: {position}) }}'
        )

    async def metadata_scan(self) -> None:
        await self._post("mutation { metadataScan(input:{}) }")

    async def metadata_clean(self) -> None:
        await self._post('mutation { metadataClean(input: {dryRun: false, paths: ""}) }')

    async def metadata_generate(self) -> None:
        await self._post("mutation { metadataGenerate(input: {}) }")

    async def metadata_auto_tag(self) -> None:
        await self._post("mutation { metadataAutoTag(input: {}) }")

    async def metadata_identify(self) -> None:
        await self._post(
            'mutation { metadataIdentify(input: { sources: [{ source: { stash_box_endpoint: "https://stashdb.org/graphql" } }] }) }'
        )


class StashLibraryCoordinator(DataUpdateCoordinator):
    """Polls library statistics every 5 minutes."""

    def __init__(self, hass: HomeAssistant, client: StashClient) -> None:
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}_library",
                         update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL))
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return {
                "scenes":     await self.client.get_scenes_count(),
                "movies":     await self.client.get_movies_count(),
                "performers": await self.client.get_performers_count(),
                "studios":    await self.client.get_studios_count(),
                "tags":       await self.client.get_tags_count(),
                "images":     await self.client.get_images_count(),
                "galleries":  await self.client.get_galleries_count(),
                "markers":    await self.client.get_markers_count(),
                "version":    await self.client.get_version(),
            }
        except Exception as err:
            raise UpdateFailed(f"Library update failed: {err}") from err


class StashPlaybackCoordinator(DataUpdateCoordinator):
    """Polls active scene state every few seconds.

    Data contract returned to entities:
        {
            "scenes":              list of streaming scene dicts (0..2),
            "active_scene_ids":    set[str] of ids confirmed by sceneStreams,
            "is_streaming":        bool,
            "active_stream_count": int,
            "last_played":         dict | None — most recent last_played scene
                                   (independent of streaming state; used for sensors),
        }

    Each scene dict includes:
        _is_streaming: bool  — True if the id appears in sceneStreams
        _last_played_at: str | None
    """

    def __init__(self, hass: HomeAssistant, client: StashClient, poll_interval: int) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN,
                         update_interval=timedelta(seconds=max(2, poll_interval)))
        self.client = client

    def _fix_paths(self, scene: dict) -> dict:
        base = self.client.stash_url
        paths = scene.get("paths") or {}
        screenshot = paths.get("screenshot")
        if screenshot:
            paths["screenshot"] = (
                screenshot
                .replace("http://localhost:9999", base)
                .replace("https://localhost:9999", base)
            )
            scene["paths"] = paths
        return scene

    async def _fetch_scene(self, scene_id: str) -> dict | None:
        data = await self.client._post(SCENE_BY_ID_QUERY, {"id": scene_id})
        scene = (data.get("data") or {}).get("findScene")
        return self._fix_paths(scene) if scene else None

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            # ── Authoritative: sceneStreams returns currently-active streams ──
            raw = await self.client._post_allow_errors(PLAYING_STATE_QUERY)
            streams = (raw.get("data") or {}).get("sceneStreams") or []
            _LOGGER.debug("sceneStreams response: %s", streams)

            streaming_ids: list[str] = []
            for stream in streams:
                m = re.search(r"/scenes?/(\d+)", stream.get("url", ""))
                if m and m.group(1) not in streaming_ids:
                    streaming_ids.append(m.group(1))
            streaming_ids = streaming_ids[:2]

            streaming_scenes: list[dict] = []
            for sid in streaming_ids:
                scene = await self._fetch_scene(sid)
                if scene:
                    scene["_is_streaming"] = True
                    streaming_scenes.append(scene)

            # ── last_played feed (for sensors + short grace-window fallback) ──
            raw2 = await self.client._post_allow_errors(ACTIVE_SCENE_QUERY)
            last_played_raw = (
                ((raw2.get("data") or {}).get("findScenes") or {}).get("scenes") or []
            )
            last_played_scene: dict | None = None
            if last_played_raw:
                last_played_scene = self._fix_paths(dict(last_played_raw[0]))

            # Grace window: sceneStreams briefly returns empty between HLS
            # segments. If the top last_played scene was touched in the last
            # few seconds, treat it as still streaming to avoid flicker.
            scenes: list[dict] = list(streaming_scenes)
            active_scene_ids = set(streaming_ids)

            if not scenes and last_played_scene:
                lp_ts = last_played_scene.get("last_played_at")
                if lp_ts:
                    try:
                        lp_dt = dt_util.parse_datetime(lp_ts)
                        if lp_dt is not None:
                            age = (dt_util.utcnow() - lp_dt).total_seconds()
                            if 0 <= age < RECENT_STREAM_GRACE_SECONDS:
                                grace_scene = dict(last_played_scene)
                                grace_scene["_is_streaming"] = True
                                scenes.append(grace_scene)
                                sid = grace_scene.get("id")
                                if sid:
                                    active_scene_ids.add(str(sid))
                    except Exception:  # noqa: BLE001
                        pass

            # Build compact last_played summary for sensors
            last_played_summary: dict | None = None
            if last_played_scene:
                studio = last_played_scene.get("studio") or {}
                performers = last_played_scene.get("performers") or []
                last_played_summary = {
                    "id": last_played_scene.get("id"),
                    "title": last_played_scene.get("title"),
                    "last_played_at": last_played_scene.get("last_played_at"),
                    "studio": studio.get("name"),
                    "performers": [
                        p.get("name") for p in performers if p.get("name")
                    ],
                    "screenshot": (last_played_scene.get("paths") or {}).get(
                        "screenshot"
                    ),
                }
        except Exception as err:
            raise UpdateFailed(f"Playback update failed: {err}") from err

        return {
            "scenes": scenes,
            "is_streaming": bool(active_scene_ids),
            "active_scene_ids": active_scene_ids,
            "active_stream_count": len(active_scene_ids),
            "last_played": last_played_summary,
        }


class StashWebhookView(HomeAssistantView):
    """Receive webhook POST from Stash and trigger immediate refresh."""

    requires_auth = False

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self.hass = hass
        self.url = f"/api/stash_player/webhook/{entry_id}"
        self.name = f"api:stash_player:webhook:{entry_id}"

    async def post(self, request: web.Request) -> web.Response:
        await request.json(content_type=None)
        data = self.hass.data.get(DOMAIN, {}).get(self.url.rsplit("/", 1)[-1], {})
        coordinator = data.get(COORDINATOR_KEY)
        if coordinator:
            self.hass.async_create_task(coordinator.async_request_refresh())
        return self.json({"ok": True})


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if entry.version < 2:
        new_data = dict(entry.data)
        if "stash_url" in new_data and CONF_URL not in new_data:
            new_data[CONF_URL] = new_data.pop("stash_url")
        hass.config_entries.async_update_entry(entry, data=new_data, version=2)
        _LOGGER.info("Migrated Stash Player config entry to version 2")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    graphql_url: str = entry.data[CONF_URL]
    api_key: str = entry.data.get(CONF_API_KEY, "")

    client = StashClient(graphql_url, session, api_key)

    poll_interval = int(entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL))
    playback = StashPlaybackCoordinator(hass, client, poll_interval)
    library = StashLibraryCoordinator(hass, client)

    try:
        await playback.async_config_entry_first_refresh()
        await library.async_config_entry_first_refresh()
    except Exception as err:
        raise ConfigEntryNotReady(str(err)) from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        COORDINATOR_KEY: playback,
        LIBRARY_COORDINATOR_KEY: library,
        CLIENT_KEY: client,
    }

    if entry.options.get(CONF_USE_WEBHOOK, False):
        view = StashWebhookView(hass, entry.entry_id)
        hass.http.register_view(view)
        hass.data[DOMAIN][entry.entry_id][WEBHOOK_VIEW_KEY] = view

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info("Stash Player connected to %s", graphql_url)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
