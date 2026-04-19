"""Media player entity for Stash Player."""

from __future__ import annotations

from datetime import datetime
from typing import Any


from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import MediaPlayerEntityFeature, MediaType
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_IDLE, STATE_PAUSED, STATE_PLAYING
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    CLIENT_KEY,
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
    )

    def __init__(self, entry: ConfigEntry, coordinator, client, index: int) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._client = client
        self._index = index
        self._position_updated_at: datetime | None = None
        self._manual_state: str | None = None
        self._cover_entity_id: str | None = None

        player_name = entry.options.get(CONF_PLAYER_NAME, DEFAULT_PLAYER_NAME)
        slot = index + 1
        self._attr_unique_id = f"{entry.entry_id}_player_{slot}"
        self._default_name = f"{player_name} {slot}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=player_name,
            manufacturer="Stash",
        )

    @property
    def name(self) -> str:
        title = self._scene.get("title")
        return title if title else self._default_name

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
        active_scene_ids = (self.coordinator.data or {}).get("active_scene_ids", set())
        if scene.get("id") in active_scene_ids:
            return STATE_PLAYING
        if self._manual_state == STATE_PLAYING:
            return STATE_PLAYING
        return STATE_IDLE

    @property
    def media_title(self) -> str:
        return self._scene.get("title", "")

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
        if not self._scene:
            return None
        if not self._cover_entity_id:
            slot = self._index + 1
            unique_id = f"{self._entry.entry_id}_cover_{slot}"
            registry = er.async_get(self.hass)
            self._cover_entity_id = registry.async_get_entity_id("image", DOMAIN, unique_id)
        return f"/api/image_proxy/{self._cover_entity_id}" if self._cover_entity_id else None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        slot = self._index + 1
        unique_id = f"{self._entry.entry_id}_cover_{slot}"
        registry = er.async_get(self.hass)
        self._cover_entity_id = registry.async_get_entity_id("image", DOMAIN, unique_id)

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
        self._manual_state = STATE_PLAYING
        self.async_write_ha_state()

    async def async_media_pause(self) -> None:
        self._manual_state = STATE_PAUSED
        self.async_write_ha_state()

    async def async_media_stop(self) -> None:
        self._manual_state = STATE_IDLE
        self.async_write_ha_state()

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
