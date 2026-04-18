"""Image entity for Stash scene cover art."""

from __future__ import annotations

import io
import logging
from datetime import datetime

_LOGGER = logging.getLogger(__name__)

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    CONF_API_KEY,
    CONF_NSFW_MODE,
    CONF_PLAYER_NAME,
    COORDINATOR_KEY,
    DEFAULT_NSFW_MODE,
    DEFAULT_PLAYER_NAME,
    DOMAIN,
    NSFW_BLUR,
    NSFW_HIDDEN,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR_KEY]
    async_add_entities([
        StashCoverImage(entry, coordinator, 0, hass),
        StashCoverImage(entry, coordinator, 1, hass),
    ])


class StashCoverImage(CoordinatorEntity, ImageEntity):
    """Static screenshot image for a Stash playback slot."""

    def __init__(self, entry: ConfigEntry, coordinator, index: int, hass: HomeAssistant) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, hass)
        self._entry = entry
        self._index = index
        player_name = entry.options.get(CONF_PLAYER_NAME, DEFAULT_PLAYER_NAME)
        slot = index + 1
        self._attr_unique_id = f"{entry.entry_id}_cover_{slot}"
        self._attr_name = f"{player_name} Cover {slot}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=player_name,
            manufacturer="Stash",
        )
        self._attr_image_last_updated: datetime | None = dt_util.utcnow()
        self._attr_content_type = "image/jpeg"

    @property
    def available(self) -> bool:
        return True

    def _handle_coordinator_update(self) -> None:
        self._attr_image_last_updated = dt_util.utcnow()
        super()._handle_coordinator_update()

    async def async_image(self) -> bytes | None:
        scenes = (self.coordinator.data or {}).get("scenes", [])
        scene = scenes[self._index] if self._index < len(scenes) else {}
        screenshot_url = (scene.get("paths") or {}).get("screenshot")
        if not screenshot_url:
            return None

        nsfw_mode = self._entry.options.get(CONF_NSFW_MODE, DEFAULT_NSFW_MODE)
        if nsfw_mode == NSFW_HIDDEN:
            return None
        if not scene.get("_is_recent", True):
            return None

        session = aiohttp_client.async_get_clientsession(self.hass)
        api_key = self._entry.data.get(CONF_API_KEY, "")
        headers = {"ApiKey": api_key} if api_key else {}
        try:
            async with session.get(screenshot_url, headers=headers) as resp:
                resp.raise_for_status()
                data = await resp.read()
        except Exception as err:
            _LOGGER.warning("Stash cover fetch failed for %s: %s", screenshot_url, err)
            return None

        if nsfw_mode == NSFW_BLUR:
            try:
                from PIL import Image
                return await self._blur_image(data)
            except ImportError:
                pass
        return data

    async def _blur_image(self, data: bytes) -> bytes:
        try:
            from PIL import Image, ImageFilter
            img = Image.open(io.BytesIO(data))
            blurred = img.filter(ImageFilter.GaussianBlur(radius=30))
            out = io.BytesIO()
            blurred.save(out, format="JPEG", quality=85)
            return out.getvalue()
        except Exception:
            return data
