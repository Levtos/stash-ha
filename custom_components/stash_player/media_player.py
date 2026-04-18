"""Media player entity for Stash Player."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import MediaPlayerEntityFeature, MediaType
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_IDLE, STATE_PAUSED, STATE_PLAYING
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    CLIENT_KEY,
    CONF_API_KEY,
    CONF_PLAYER_NAME,
    COORDINATOR_KEY,
    DEFAULT_PLAYER_NAME,
    DOMAIN,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data[COORDINATOR_KEY]
    client = data[CLIENT_KEY]
    async_add_entities([
        StashMediaPlayer(entry, coordinator, client, 0),
        StashMediaPlayer(entry, coordinator, client, 1),
    ])


class StashMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    """Representation of a Stash media player slot."""

    _attr_media_content_type = MediaType.VIDEO
    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.SEEK
        | MediaPlayerEntityFeature.VOLUME_SET
    )

    def __init__(self, entry: ConfigEntry, coordinator, client, index: int) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._client = client
        self._index = index
        self._position_updated_at: datetime | None = None
        self._manual_state: str | None = None

        player_name = entry.options.get(CONF_PLAYER_NAME, DEFAULT_PLAYER_NAME)
        slot = index + 1
        self._attr_unique_id = f"{entry.entry_id}_player_{slot}"
        self._attr_name = f"{player_name} {slot}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=player_name,
            manufacturer="Stash",
        )

    @property
    def _scene(self) -> dict[str, Any]:
        scenes = (self.coordinator.data or {}).get("scenes", [])
        return scenes[self._index] if self._index < len(scenes) else {}

    @property
    def state(self) -> str | None:
        scene = self._scene
        if not scene:
            return STATE_IDLE
        if self._manual_state in (STATE_PAUSED, STATE_IDLE):
            return self._manual_state
        resume_time = float(scene.get("resume_time", 0) or 0)
        is_streaming = bool((self.coordinator.data or {}).get("is_streaming"))
        if resume_time > 0 and is_streaming:
            return STATE_PLAYING
        return STATE_IDLE

    @property
    def media_title(self) -> str:
        return self._scene.get("title", "Unknown")

    @property
    def media_artist(self) -> str:
        performers = self._scene.get("performers", [])
        return ", ".join(p.get("name", "") for p in performers if p.get("name"))

    @property
    def media_album_name(self) -> str:
        studio = self._scene.get("studio")
        return studio.get("name", "") if studio else ""

    @property
    def media_duration(self) -> float:
        files = self._scene.get("files", [])
        return float(files[0].get("duration", 0)) if files else 0

    @property
    def media_position(self) -> float:
        return float(self._scene.get("resume_time", 0) or 0)

    @property
    def media_position_updated_at(self):
        return self._position_updated_at or dt_util.utcnow()

    @property
    def entity_picture(self) -> str | None:
        screenshot = (self._scene.get("paths") or {}).get("screenshot")
        if not screenshot:
            return None
        api_key = self._entry.data.get(CONF_API_KEY, "")
        return f"{screenshot}?apikey={api_key}" if api_key else screenshot

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        scene = self._scene
        if not scene:
            return {}
        tags = scene.get("tags", [])
        files = scene.get("files", [])
        studio = scene.get("studio")
        scene_id = scene.get("id")
        rating100 = scene.get("rating100")
        resolution = None
        if files:
            width = files[0].get("width")
            height = files[0].get("height")
            if width and height:
                resolution = f"{width}x{height}"
        return {
            "stash_scene_id": scene_id,
            "stash_url": f"{self._client.stash_url}/scenes/{scene_id}" if scene_id else None,
            "stash_rating": (rating100 / 20) if rating100 is not None else None,
            "stash_tags": [t.get("name") for t in tags if t.get("name")],
            "stash_studio": studio.get("name") if studio else None,
            "stash_resolution": resolution,
            "stash_play_count": scene.get("play_count"),
        }

    async def async_media_play(self) -> None:
        scene_id = self._scene.get("id")
        if scene_id:
            await self._client.generate_screenshot(scene_id)
        self._manual_state = STATE_PLAYING
        self.async_write_ha_state()

    async def async_media_pause(self) -> None:
        self._manual_state = STATE_PAUSED
        self.async_write_ha_state()

    async def async_media_stop(self) -> None:
        self._manual_state = STATE_IDLE
        self.async_write_ha_state()

    async def async_set_volume_level(self, volume: float) -> None:
        pass

    async def async_media_seek(self, position: float) -> None:
        scene_id = self._scene.get("id")
        if not scene_id:
            return
        await self._client.save_activity(scene_id, float(position))
        self._position_updated_at = dt_util.utcnow()
        self._manual_state = None
        self.async_write_ha_state()

    def _handle_coordinator_update(self) -> None:
        self._manual_state = None
        self._position_updated_at = dt_util.utcnow()
        super()._handle_coordinator_update()
