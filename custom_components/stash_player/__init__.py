"""Stash Player integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ACTIVE_SCENE_QUERY,
    CLIENT_KEY,
    CONF_DEBUG_LOGGING,
    CONF_POLL_INTERVAL,
    CONF_STASH_URL,
    CONF_USE_WEBHOOK,
    COORDINATOR_KEY,
    DEFAULT_DEBUG_LOGGING,
    DEFAULT_LIBRARY_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    LIBRARY_COORDINATOR_KEY,
    PLATFORMS,
    PLAYING_STATE_QUERY,
    STASH_STATS_QUERY,
    STASH_VERSION_QUERY,
    WEBHOOK_VIEW_KEY,
)
from .graphql import StashConnectionError, StashGraphQLClient, StashGraphQLError

_LOGGER = logging.getLogger(__name__)
SERVICE_DEBUG_CONNECTION = "debug_connection"


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
            _LOGGER.error("Coordinator update failed: %s", err)
            raise UpdateFailed(f"Failed to update from Stash: {err}") from err

        stats: dict[str, Any] = {}
        version: str | None = None

        try:
            stats_data = await self.client.query(STASH_STATS_QUERY)
            stats = {
                "scenes": (stats_data.get("findScenes") or {}).get("count"),
                "movies": (stats_data.get("findMovies") or {}).get("count"),
                "performers": (stats_data.get("findPerformers") or {}).get("count"),
                "studios": (stats_data.get("findStudios") or {}).get("count"),
                "tags": (stats_data.get("findTags") or {}).get("count"),
                "images": (stats_data.get("findImages") or {}).get("count"),
                "galleries": (stats_data.get("findGalleries") or {}).get("count"),
                "markers": (stats_data.get("findSceneMarkers") or {}).get("count"),
            }
        except StashGraphQLError as err:
            _LOGGER.debug("Stats query unavailable on this Stash instance: %s", err)

        try:
            version_data = await self.client.query(STASH_VERSION_QUERY)
            version = (version_data.get("version") or {}).get("version")
        except StashGraphQLError as err:
            _LOGGER.debug("Version query unavailable on this Stash instance: %s", err)

        scenes = scene_data.get("findScenes", {}).get("scenes", [])
        scene = scenes[0] if scenes else None
        streams = playing_data.get("sceneStreams") or []
        return {
            "scene": scene,
            "is_streaming": bool(streams),
            "streams": streams,
            **stats,
            "version": version,
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


async def _async_handle_debug_connection(hass: HomeAssistant, call: ServiceCall) -> None:
    """Manual service for debugging connectivity issues."""
    entry_id: str | None = call.data.get("entry_id")
    entries = hass.data.get(DOMAIN, {})

    if entry_id:
        targets = [(entry_id, entries.get(entry_id))]
    else:
        targets = list(entries.items())

    if not targets:
        _LOGGER.warning("No stash_player entries available for debug_connection")
        return

    for target_entry_id, data in targets:
        if not data:
            _LOGGER.warning("Entry %s not found for debug_connection", target_entry_id)
            continue

        client: StashGraphQLClient = data[CLIENT_KEY]
        _LOGGER.info("Running stash_player debug_connection for entry=%s url=%s endpoint=%s", target_entry_id, client.stash_url, client.endpoint)
        try:
            await client.validate_connection()
            _LOGGER.info("stash_player debug_connection successful for entry=%s", target_entry_id)
        except Exception as err:
            _LOGGER.error("stash_player debug_connection failed for entry=%s: %s", target_entry_id, err)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Stash Player from a config entry."""
    session = aiohttp_client.async_get_clientsession(hass)
    stash_url: str = entry.data[CONF_STASH_URL]
    api_key: str = entry.data.get(CONF_API_KEY, "")

    debug_logging = bool(entry.options.get(CONF_DEBUG_LOGGING, DEFAULT_DEBUG_LOGGING))
    client = StashGraphQLClient(session, stash_url, api_key, debug_logging=debug_logging)

    poll_interval = int(entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL))

    playback_coordinator = StashCoordinator(hass, client, poll_interval)
    library_coordinator = StashLibraryCoordinator(hass, client)

    try:
        await playback_coordinator.async_config_entry_first_refresh()
        await library_coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.error("Initial Stash refresh failed for %s: %s", stash_url, err)
        raise ConfigEntryNotReady(str(err)) from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        COORDINATOR_KEY: playback_coordinator,
        LIBRARY_COORDINATOR_KEY: library_coordinator,
        CLIENT_KEY: client,
    }

    if not hass.services.has_service(DOMAIN, SERVICE_DEBUG_CONNECTION):
        async def _debug_service(call: ServiceCall) -> None:
            await _async_handle_debug_connection(hass, call)

        hass.services.async_register(DOMAIN, SERVICE_DEBUG_CONNECTION, _debug_service)

    if entry.options.get(CONF_USE_WEBHOOK, False):
        view = StashWebhookView(hass, entry.entry_id)
        hass.http.register_view(view)
        hass.data[DOMAIN][entry.entry_id][WEBHOOK_VIEW_KEY] = view

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info("stash_player setup complete for %s", stash_url)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data.get(DOMAIN) and hass.services.has_service(DOMAIN, SERVICE_DEBUG_CONNECTION):
            hass.services.async_remove(DOMAIN, SERVICE_DEBUG_CONNECTION)
    return unload_ok
