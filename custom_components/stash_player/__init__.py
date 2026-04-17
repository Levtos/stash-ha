"""Stash Player integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ACTIVE_SCENE_QUERY,
    CLIENT_KEY,
    CONF_POLL_INTERVAL,
    CONF_STASH_URL,
    CONF_USE_WEBHOOK,
    COORDINATOR_KEY,
    DEFAULT_LIBRARY_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    LIBRARY_COORDINATOR_KEY,
    PLATFORMS,
    PLAYING_STATE_QUERY,
    WEBHOOK_VIEW_KEY,
)
from .graphql import StashConnectionError, StashGraphQLClient, StashGraphQLError

_LOGGER = logging.getLogger(__name__)


class StashCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls active scene state every few seconds."""

    def __init__(self, hass: HomeAssistant, client: StashGraphQLClient, poll_interval: int) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=max(2, poll_interval)),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            scene_data = await self.client.query(ACTIVE_SCENE_QUERY)
            playing_data = await self.client.query(PLAYING_STATE_QUERY)
        except (StashConnectionError, StashGraphQLError) as err:
            raise UpdateFailed(f"Failed to update from Stash: {err}") from err

        scenes = scene_data.get("findScenes", {}).get("scenes", [])
        streams = playing_data.get("sceneStreams") or []
        return {
            "scenes": scenes,
            "is_streaming": bool(streams),
            "streams": streams,
        }


class StashLibraryCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls library statistics every 5 minutes."""

    def __init__(self, hass: HomeAssistant, client: StashGraphQLClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_library",
            update_interval=timedelta(seconds=DEFAULT_LIBRARY_POLL_INTERVAL),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            scenes = await self.client.async_get_scenes_count()
            movies = await self.client.async_get_movies_count()
            performers = await self.client.async_get_performers_count()
            studios = await self.client.async_get_studios_count()
            tags = await self.client.async_get_tags_count()
            images = await self.client.async_get_images_count()
            galleries = await self.client.async_get_galleries_count()
            markers = await self.client.async_get_markers_count()
            version = await self.client.async_get_version()
        except (StashConnectionError, StashGraphQLError) as err:
            raise UpdateFailed(f"Library stats update failed: {err}") from err

        return {
            "scenes": scenes,
            "movies": movies,
            "performers": performers,
            "studios": studios,
            "tags": tags,
            "images": images,
            "galleries": galleries,
            "markers": markers,
            "version": version,
        }


class StashWebhookView(HomeAssistantView):
    """Receive webhook events from Stash and refresh coordinator."""

    requires_auth = False

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self.hass = hass
        self.url = f"/api/stash_player/webhook/{entry_id}"
        self.name = f"api:stash_player:webhook:{entry_id}"

    async def post(self, request: web.Request) -> web.Response:
        """Handle webhook POST from Stash."""
        _payload = await request.json(content_type=None)
        entry_id = self.url.rsplit("/", 1)[-1]
        entry_data = self.hass.data.get(DOMAIN, {}).get(entry_id, {})
        coordinator: StashCoordinator | None = entry_data.get(COORDINATOR_KEY)
        if coordinator:
            self.hass.async_create_task(coordinator.async_request_refresh())
        return self.json({"ok": True})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Stash Player from a config entry."""
    session = aiohttp_client.async_get_clientsession(hass)
    stash_url: str = entry.data[CONF_STASH_URL]
    api_key: str = entry.data.get(CONF_API_KEY, "")

    client = StashGraphQLClient(session, stash_url, api_key)
    poll_interval = int(entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL))

    playback_coordinator = StashCoordinator(hass, client, poll_interval)
    library_coordinator = StashLibraryCoordinator(hass, client)

    try:
        await playback_coordinator.async_config_entry_first_refresh()
        await library_coordinator.async_config_entry_first_refresh()
    except Exception as err:
        raise ConfigEntryNotReady(str(err)) from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        COORDINATOR_KEY: playback_coordinator,
        LIBRARY_COORDINATOR_KEY: library_coordinator,
        CLIENT_KEY: client,
    }

    if entry.options.get(CONF_USE_WEBHOOK, False):
        view = StashWebhookView(hass, entry.entry_id)
        hass.http.register_view(view)
        hass.data[DOMAIN][entry.entry_id][WEBHOOK_VIEW_KEY] = view

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
