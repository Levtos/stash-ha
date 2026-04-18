"""Camera entity for Stash scene cover image."""

from __future__ import annotations

import io

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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
        StashCoverCamera(entry, coordinator, 0),
        StashCoverCamera(entry, coordinator, 1),
    ])


class StashCoverCamera(CoordinatorEntity, Camera):
    """Proxy camera for Stash screenshot with optional content filtering."""

    def __init__(self, entry: ConfigEntry, coordinator, index: int) -> None:
        super().__init__(coordinator)
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

    @property
    def available(self) -> bool:
        return True

    async def async_camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None:
        scenes = (self.coordinator.data or {}).get("scenes", [])
        scene = scenes[self._index] if self._index < len(scenes) else {}
        screenshot_url = (scene.get("paths") or {}).get("screenshot")
        if not screenshot_url:
            return self._placeholder_image()

        nsfw_mode = self._entry.options.get(CONF_NSFW_MODE, DEFAULT_NSFW_MODE)
        if nsfw_mode == NSFW_HIDDEN:
            return self._placeholder_image()

        session = aiohttp_client.async_get_clientsession(self.hass)
        api_key = self._entry.data.get(CONF_API_KEY, "")
        headers = {"ApiKey": api_key} if api_key else {}
        try:
            async with session.get(screenshot_url, headers=headers) as response:
                response.raise_for_status()
                image_data = await response.read()
        except Exception:
            return self._placeholder_image()

        if nsfw_mode == NSFW_BLUR:
            return await self._blur_image(image_data)
        return image_data

    async def _blur_image(self, data: bytes) -> bytes:
        try:
            from PIL import Image, ImageFilter
            img = Image.open(io.BytesIO(data))
            blurred = img.filter(ImageFilter.GaussianBlur(radius=30))
            output = io.BytesIO()
            blurred.save(output, format="JPEG", quality=85)
            return output.getvalue()
        except Exception:
            return data

    def _placeholder_image(self) -> bytes:
        return (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0bIDATx\x9cc\x00\x01"
            b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
