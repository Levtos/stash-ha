"""Entities für Stash HA: 9 library sensors + 4 playback sensors + 1 image
+ 1 media_player.
"""
from __future__ import annotations

import io
import logging
from datetime import datetime
from typing import Any

from homeassistant.components.image import ImageEntity
from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MediaPlayerEntityFeature,
    MediaType,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_IDLE, STATE_PLAYING, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    CONF_API_KEY,
    CONF_NSFW_MODE,
    CONF_PLAYER_NAME,
    DEFAULT_NSFW_MODE,
    DEFAULT_PLAYER_NAME,
    DOMAIN,
    MODULE_ID,
    NSFW_BLUR,
    NSFW_HIDDEN,
    SLOT_COUNT,
    SLOT_EMPTY_TITLE,
    UID_ACTIVE_STREAMS,
    UID_COVER,
    UID_CURRENTLY_PLAYING,
    UID_GALLERIES,
    UID_IMAGES,
    UID_LAST_PLAYED_AT,
    UID_LAST_PLAYED_TITLE,
    UID_MARKERS,
    UID_MOVIES,
    UID_PERFORMERS,
    UID_PLAYER,
    UID_SCENES,
    UID_STUDIOS,
    UID_TAGS,
    UID_VERSION,
    uid_slot_cover,
    uid_slot_display_text,
    uid_slot_media_player,
    uid_slot_performers,
    uid_slot_studio,
    uid_slot_tags,
    uid_slot_title,
    unique_id,
)
from .coordinator import (
    StashLibraryCoordinator,
    StashPlaybackCoordinator,
    runtime_from_hass,
)
from .playback_logic import (
    current_playing_title,
    slot_cover_url,
    slot_display_text,
    slot_performers,
    slot_studio,
    slot_tags,
    slot_title,
)

_LOGGER = logging.getLogger(__name__)


def _device_info(entry: ConfigEntry) -> DeviceInfo:
    player_name = entry.options.get(CONF_PLAYER_NAME, DEFAULT_PLAYER_NAME)
    return DeviceInfo(
        identifiers={(DOMAIN, f"{MODULE_ID}_{entry.entry_id}")},
        name=player_name,
        manufacturer="Stash",
        model="Stash Player",
    )


async def async_get_entities(
    hass: HomeAssistant, entry: ConfigEntry, platform: Platform
) -> list:
    runtime = runtime_from_hass(hass, entry.entry_id)
    if runtime is None:
        return []
    library: StashLibraryCoordinator = runtime["library"]
    playback: StashPlaybackCoordinator = runtime["playback"]
    client = runtime["client"]

    if platform == Platform.SENSOR:
        return [
            _LibCountSensor(library, entry, UID_SCENES, "Scenes", "mdi:filmstrip", "scenes"),
            _LibCountSensor(library, entry, UID_MOVIES, "Movies", "mdi:movie-open-outline", "movies"),
            _LibCountSensor(library, entry, UID_PERFORMERS, "Performers", "mdi:account-multiple", "performers"),
            _LibCountSensor(library, entry, UID_STUDIOS, "Studios", "mdi:office-building", "studios"),
            _LibCountSensor(library, entry, UID_TAGS, "Tags", "mdi:tag-multiple", "tags"),
            _LibCountSensor(library, entry, UID_IMAGES, "Images", "mdi:image-multiple-outline", "images"),
            _LibCountSensor(library, entry, UID_GALLERIES, "Galleries", "mdi:image-album", "galleries"),
            _LibCountSensor(library, entry, UID_MARKERS, "Markers", "mdi:bookmark-multiple-outline", "markers"),
            _VersionSensor(library, entry),
            _ActiveStreamCountSensor(playback, entry),
            _CurrentlyPlayingSensor(playback, entry),
            _LastPlayedTitleSensor(playback, entry),
            _LastPlayedAtSensor(playback, entry),
            *(
                _SlotTitleSensor(playback, entry, n)
                for n in range(1, SLOT_COUNT + 1)
            ),
            *(
                _SlotMetaSensor(playback, entry, n, kind)
                for n in range(1, SLOT_COUNT + 1)
                for kind in _SLOT_META
            ),
        ]
    if platform == Platform.IMAGE:
        return [
            _CoverImage(playback, entry, hass),
            *(
                _SlotCoverImage(playback, entry, hass, n)
                for n in range(1, SLOT_COUNT + 1)
            ),
        ]
    if platform == Platform.MEDIA_PLAYER:
        return [
            _MediaPlayer(playback, entry, client),
            *(
                _SlotMediaPlayer(playback, entry, client, n)
                for n in range(1, SLOT_COUNT + 1)
            ),
        ]
    return []


# ------------------------------------------------------------- library sensors


class _LibCountSensor(CoordinatorEntity[StashLibraryCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: StashLibraryCoordinator,
        entry: ConfigEntry,
        suffix: str,
        name: str,
        icon: str,
        data_key: str,
    ) -> None:
        super().__init__(coordinator)
        self._key = data_key
        self._attr_unique_id = unique_id(MODULE_ID, entry.entry_id, suffix)
        self._attr_name = name
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = "items"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get(self._key)


class _VersionSensor(CoordinatorEntity[StashLibraryCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:information-outline"

    def __init__(self, coordinator: StashLibraryCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = unique_id(MODULE_ID, entry.entry_id, UID_VERSION)
        self._attr_name = "Version"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get("version")


# ----------------------------------------------------------- playback sensors


class _ActiveStreamCountSensor(CoordinatorEntity[StashPlaybackCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:play-network"
    _attr_native_unit_of_measurement = "streams"

    def __init__(self, coordinator: StashPlaybackCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = unique_id(MODULE_ID, entry.entry_id, UID_ACTIVE_STREAMS)
        self._attr_name = "Active Streams"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> int:
        return int((self.coordinator.data or {}).get("active_stream_count", 0) or 0)


class _CurrentlyPlayingSensor(CoordinatorEntity[StashPlaybackCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:play-box-multiple"

    def __init__(self, coordinator: StashPlaybackCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = unique_id(MODULE_ID, entry.entry_id, UID_CURRENTLY_PLAYING)
        self._attr_name = "Currently Playing"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> str | None:
        # Multiple active scenes are separate titles — never join them into a
        # combined "A | B" state (that would make Title Classifier store a bogus
        # A|B catalog entry). The most-recently-active title only; the separate
        # titles stay in extra_state_attributes below.
        scenes = (self.coordinator.data or {}).get("scenes") or []
        return current_playing_title(scenes)

    @property
    def extra_state_attributes(self) -> dict:
        scenes = (self.coordinator.data or {}).get("scenes") or []
        return {
            "titles": [s.get("title") for s in scenes if s.get("title")],
            "scene_ids": [str(s.get("id")) for s in scenes if s.get("id")],
            "count": len(scenes),
        }


class _SlotTitleSensor(CoordinatorEntity[StashPlaybackCoordinator], SensorEntity):
    """Fixed slot sensor: the title of the scene stuck to this slot, or None.

    One observable state per active scene so the Title Classifier can watch each
    active stream as a separate source. Empty slots report None — never an
    "idle" string — so no bogus catalog entry is created. Slot assignment is
    sticky (see playback_logic.assign_slots): a scene keeps its slot until it
    stops, so the state does not flap when the scene order changes.
    """

    _attr_has_entity_name = True
    _attr_icon = "mdi:play-box-outline"

    def __init__(
        self,
        coordinator: StashPlaybackCoordinator,
        entry: ConfigEntry,
        slot: int,
    ) -> None:
        super().__init__(coordinator)
        self._slot = slot
        self._attr_unique_id = unique_id(
            MODULE_ID, entry.entry_id, uid_slot_title(slot)
        )
        self._attr_name = f"Slot {slot} Title"
        self._attr_device_info = _device_info(entry)

    @property
    def _scene(self) -> dict[str, Any] | None:
        slots = (self.coordinator.data or {}).get("slots") or {}
        return slots.get(self._slot)

    @property
    def native_value(self) -> str:
        # Empty slot ⇒ the fixed placeholder (meant for the TC ignore list),
        # never None/"Unbekannt".
        return slot_title(self._scene, SLOT_EMPTY_TITLE)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        scene = self._scene
        if not scene:
            return {"slot": self._slot, "scene_id": None}
        studio = scene.get("studio") or {}
        performers = scene.get("performers") or []
        tags = scene.get("tags") or []
        scene_id = scene.get("id")
        return {
            "slot": self._slot,
            "scene_id": str(scene_id) if scene_id is not None else None,
            "title": scene.get("title"),
            "cover_url": (scene.get("paths") or {}).get("screenshot"),
            "studio": studio.get("name"),
            "performers": [p.get("name") for p in performers if p.get("name")],
            "tags": [t.get("name") for t in tags if t.get("name")],
            "last_played_at": scene.get("last_played_at"),
            "resume_time": scene.get("resume_time"),
        }


# kind -> (name, icon, formatter, uid_suffix_fn)
_SLOT_META = {
    "studio": ("Studio", "mdi:office-building", slot_studio, uid_slot_studio),
    "performers": ("Performers", "mdi:account-multiple", slot_performers, uid_slot_performers),
    "tags": ("Tags", "mdi:tag-multiple", slot_tags, uid_slot_tags),
    "display_text": ("Display Text", "mdi:card-text", slot_display_text, uid_slot_display_text),
}


class _SlotMetaSensor(CoordinatorEntity[StashPlaybackCoordinator], SensorEntity):
    """Per-slot metadata text sensor (studio / performers / tags / display text).

    Reuses the sticky slot data from the coordinator; empty slots report the
    fixed placeholder instead of None/"Unbekannt".
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: StashPlaybackCoordinator,
        entry: ConfigEntry,
        slot: int,
        kind: str,
    ) -> None:
        super().__init__(coordinator)
        self._slot = slot
        name, icon, self._fmt, uid_fn = _SLOT_META[kind]
        self._attr_unique_id = unique_id(MODULE_ID, entry.entry_id, uid_fn(slot))
        self._attr_name = f"Slot {slot} {name}"
        self._attr_icon = icon
        self._attr_device_info = _device_info(entry)

    @property
    def _scene(self) -> dict[str, Any] | None:
        slots = (self.coordinator.data or {}).get("slots") or {}
        return slots.get(self._slot)

    @property
    def native_value(self) -> str | None:
        return self._fmt(self._scene, SLOT_EMPTY_TITLE)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        scene = self._scene
        scene_id = scene.get("id") if scene else None
        return {
            "slot": self._slot,
            "scene_id": str(scene_id) if scene_id is not None else None,
        }


class _LastPlayedTitleSensor(CoordinatorEntity[StashPlaybackCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:history"

    def __init__(self, coordinator: StashPlaybackCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = unique_id(MODULE_ID, entry.entry_id, UID_LAST_PLAYED_TITLE)
        self._attr_name = "Last Played"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> str | None:
        lp = (self.coordinator.data or {}).get("last_played") or {}
        return lp.get("title") or None

    @property
    def extra_state_attributes(self) -> dict:
        lp = (self.coordinator.data or {}).get("last_played") or {}
        return {
            "stash_scene_id": lp.get("id"),
            "studio": lp.get("studio"),
            "performers": lp.get("performers") or [],
            "last_played_at": lp.get("last_played_at"),
            "screenshot": lp.get("screenshot"),
        }


class _LastPlayedAtSensor(CoordinatorEntity[StashPlaybackCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:clock-outline"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: StashPlaybackCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = unique_id(MODULE_ID, entry.entry_id, UID_LAST_PLAYED_AT)
        self._attr_name = "Last Played At"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> datetime | None:
        lp = (self.coordinator.data or {}).get("last_played") or {}
        raw = lp.get("last_played_at")
        if not raw:
            return None
        parsed = dt_util.parse_datetime(raw)
        if parsed is None:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt_util.UTC)
        return parsed


# ------------------------------------------------------------------ image


async def _blur_image_bytes(data: bytes) -> bytes:
    try:
        from PIL import Image, ImageFilter
    except ImportError:
        return data
    try:
        img = Image.open(io.BytesIO(data))
        blurred = img.filter(ImageFilter.GaussianBlur(radius=30))
        if img.mode in ("RGBA", "P"):
            blurred = blurred.convert("RGB")
        out = io.BytesIO()
        blurred.save(out, format="JPEG", quality=85)
        return out.getvalue()
    except Exception:  # noqa: BLE001
        return data


async def _fetch_cover_bytes(
    hass: HomeAssistant, entry: ConfigEntry, screenshot_url: str | None
) -> bytes | None:
    """Fetch (and NSFW-process) a scene screenshot. Shared by the global cover
    and the per-slot covers. Returns None when there is nothing to show or the
    fetch fails (never raises)."""
    if not screenshot_url:
        return None
    nsfw_mode = entry.options.get(CONF_NSFW_MODE, DEFAULT_NSFW_MODE)
    if nsfw_mode == NSFW_HIDDEN:
        return None
    session = aiohttp_client.async_get_clientsession(hass)
    api_key = entry.data.get(CONF_API_KEY, "")
    headers = {"ApiKey": api_key} if api_key else {}
    try:
        async with session.get(screenshot_url, headers=headers) as resp:
            resp.raise_for_status()
            data = await resp.read()
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Stash cover fetch failed for %s: %s", screenshot_url, err)
        return None
    if nsfw_mode == NSFW_BLUR:
        try:
            return await _blur_image_bytes(data)
        except Exception:  # noqa: BLE001
            return data
    return data


class _CoverImage(CoordinatorEntity[StashPlaybackCoordinator], ImageEntity):
    """Cover of the most-recently-active Stash stream."""

    def __init__(
        self,
        coordinator: StashPlaybackCoordinator,
        entry: ConfigEntry,
        hass: HomeAssistant,
    ) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, hass)
        self._entry = entry
        self._last_scene_id: str | None = None
        self._last_streaming: bool = False
        player_name = entry.options.get(CONF_PLAYER_NAME, DEFAULT_PLAYER_NAME)
        self._attr_unique_id = unique_id(MODULE_ID, entry.entry_id, UID_COVER)
        self._attr_name = f"{player_name} Cover"
        self._attr_content_type = "image/jpeg"
        self._attr_device_info = _device_info(entry)
        self._attr_image_last_updated: datetime | None = None

    @property
    def _scene(self) -> dict:
        scenes = (self.coordinator.data or {}).get("scenes") or []
        return scenes[0] if scenes else {}

    @property
    def _is_streaming(self) -> bool:
        return bool((self.coordinator.data or {}).get("scenes"))

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    def _handle_coordinator_update(self) -> None:
        scene_id = self._scene.get("id") if self._scene else None
        is_streaming_now = self._is_streaming
        if scene_id != self._last_scene_id or is_streaming_now != self._last_streaming:
            self._last_scene_id = scene_id
            self._last_streaming = is_streaming_now
            self._attr_image_last_updated = dt_util.utcnow() if is_streaming_now else None
        super()._handle_coordinator_update()

    async def async_image(self) -> bytes | None:
        if not self._is_streaming:
            return None
        screenshot_url = (self._scene.get("paths") or {}).get("screenshot")
        return await _fetch_cover_bytes(self.hass, self._entry, screenshot_url)


class _SlotCoverImage(CoordinatorEntity[StashPlaybackCoordinator], ImageEntity):
    """Cover/screenshot of the scene stuck to this slot. Empty slot ⇒ no image."""

    def __init__(
        self,
        coordinator: StashPlaybackCoordinator,
        entry: ConfigEntry,
        hass: HomeAssistant,
        slot: int,
    ) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, hass)
        self._entry = entry
        self._slot = slot
        self._last_scene_id: str | None = None
        self._attr_unique_id = unique_id(MODULE_ID, entry.entry_id, uid_slot_cover(slot))
        self._attr_name = f"Slot {slot} Cover"
        self._attr_content_type = "image/jpeg"
        self._attr_device_info = _device_info(entry)
        self._attr_image_last_updated: datetime | None = None

    @property
    def _scene(self) -> dict[str, Any] | None:
        slots = (self.coordinator.data or {}).get("slots") or {}
        return slots.get(self._slot)

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    def _handle_coordinator_update(self) -> None:
        scene = self._scene
        scene_id = str(scene.get("id")) if scene and scene.get("id") is not None else None
        if scene_id != self._last_scene_id:
            self._last_scene_id = scene_id
            self._attr_image_last_updated = dt_util.utcnow() if scene_id else None
        super()._handle_coordinator_update()

    async def async_image(self) -> bytes | None:
        return await _fetch_cover_bytes(self.hass, self._entry, slot_cover_url(self._scene))


# --------------------------------------------------------------- media_player


class _MediaPlayer(CoordinatorEntity[StashPlaybackCoordinator], MediaPlayerEntity):
    """Display-only media player surfacing the most-recent active Stash stream."""

    _attr_media_content_type = MediaType.VIDEO
    _attr_supported_features = MediaPlayerEntityFeature(0)
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: StashPlaybackCoordinator,
        entry: ConfigEntry,
        client,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._client = client
        self._cover_entity_id: str | None = None
        self._last_scene_id: str | None = None
        self._position_updated_at: datetime | None = None

        player_name = entry.options.get(CONF_PLAYER_NAME, DEFAULT_PLAYER_NAME)
        self._attr_unique_id = unique_id(MODULE_ID, entry.entry_id, UID_PLAYER)
        self._attr_name = player_name
        self._attr_device_info = _device_info(entry)

    @property
    def _scenes(self) -> list[dict[str, Any]]:
        return (self.coordinator.data or {}).get("scenes") or []

    @property
    def _scene(self) -> dict[str, Any]:
        scenes = self._scenes
        return scenes[0] if scenes else {}

    @property
    def _is_streaming(self) -> bool:
        return bool(self._scenes)

    def _resolve_cover_entity(self) -> str | None:
        if self._cover_entity_id:
            return self._cover_entity_id
        if self.hass is None:
            return None
        cover_uid = unique_id(MODULE_ID, self._entry.entry_id, UID_COVER)
        registry = er.async_get(self.hass)
        self._cover_entity_id = registry.async_get_entity_id("image", DOMAIN, cover_uid)
        return self._cover_entity_id

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def state(self) -> str:
        return STATE_PLAYING if self._is_streaming else STATE_IDLE

    @property
    def media_title(self) -> str | None:
        return self._scene.get("title") if self._is_streaming else None

    @property
    def media_artist(self) -> str | None:
        if not self._is_streaming:
            return None
        performers = self._scene.get("performers") or []
        names = [p.get("name") for p in performers if p.get("name")]
        return ", ".join(names) or None

    @property
    def media_album_name(self) -> str | None:
        if not self._is_streaming:
            return None
        studio = self._scene.get("studio") or {}
        return studio.get("name") or None

    @property
    def media_content_id(self) -> str | None:
        if not self._is_streaming:
            return None
        sid = self._scene.get("id")
        return str(sid) if sid else None

    @property
    def media_duration(self) -> int | None:
        if not self._is_streaming:
            return None
        files = self._scene.get("files") or []
        if not files:
            return None
        duration = files[0].get("duration")
        return int(duration) if duration else None

    @property
    def media_position(self) -> int | None:
        if not self._is_streaming:
            return None
        resume = self._scene.get("resume_time") or 0
        try:
            return int(float(resume))
        except (TypeError, ValueError):
            return None

    @property
    def media_position_updated_at(self) -> datetime | None:
        return self._position_updated_at if self._is_streaming else None

    @property
    def media_image_url(self) -> str | None:
        if not self._is_streaming:
            return None
        return (self._scene.get("paths") or {}).get("screenshot")

    @property
    def entity_picture(self) -> str | None:
        if not self._is_streaming:
            return None
        cover = self._resolve_cover_entity()
        if cover and self.hass is not None:
            cover_state = self.hass.states.get(cover)
            if cover_state is not None:
                pic = cover_state.attributes.get("entity_picture")
                if pic:
                    return pic
        return self.media_image_url

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        scenes = self._scenes
        attrs: dict[str, Any] = {
            "active_stream_count": data.get("active_stream_count", 0),
            "is_streaming": self._is_streaming,
            "active_titles": [s.get("title") for s in scenes if s.get("title")],
        }
        scene = self._scene
        if not scene:
            return attrs

        tags = scene.get("tags") or []
        files = scene.get("files") or []
        studio = scene.get("studio") or {}
        scene_id = scene.get("id")
        rating100 = scene.get("rating100")

        resolution = None
        if files:
            width = files[0].get("width")
            height = files[0].get("height")
            if width and height:
                resolution = f"{width}x{height}"

        attrs.update({
            "stash_scene_id": scene_id,
            "stash_url": (
                f"{self._client.stash_url}/scenes/{scene_id}" if scene_id else None
            ),
            "stash_rating": (rating100 / 20) if rating100 is not None else None,
            "stash_tags": [t.get("name") for t in tags if t.get("name")],
            "stash_studio": studio.get("name") if studio else None,
            "stash_resolution": resolution,
            "stash_play_count": scene.get("play_count"),
            "stash_last_played_at": scene.get("last_played_at"),
        })
        return attrs

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._resolve_cover_entity()

    def _handle_coordinator_update(self) -> None:
        scene_id = self._scene.get("id") if self._scene else None
        if scene_id != self._last_scene_id:
            self._last_scene_id = scene_id
            self._position_updated_at = dt_util.utcnow() if self._is_streaming else None
        elif self._is_streaming and self._position_updated_at is None:
            self._position_updated_at = dt_util.utcnow()
        elif not self._is_streaming:
            self._position_updated_at = None
        super()._handle_coordinator_update()


class _SlotMediaPlayer(CoordinatorEntity[StashPlaybackCoordinator], MediaPlayerEntity):
    """Display-only per-slot media player (no real control; supported_features=0).

    A dashboard tile for the scene stuck to this slot. Empty slot ⇒ idle with the
    fixed placeholder title and no cover. Does NOT implement any play/pause/seek/
    volume services — it never pretends to control the stream.
    """

    _attr_media_content_type = MediaType.VIDEO
    _attr_supported_features = MediaPlayerEntityFeature(0)
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: StashPlaybackCoordinator,
        entry: ConfigEntry,
        client,
        slot: int,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._client = client
        self._slot = slot
        self._cover_entity_id: str | None = None
        self._attr_unique_id = unique_id(
            MODULE_ID, entry.entry_id, uid_slot_media_player(slot)
        )
        self._attr_name = f"Slot {slot}"
        self._attr_device_info = _device_info(entry)

    @property
    def _scene(self) -> dict[str, Any] | None:
        slots = (self.coordinator.data or {}).get("slots") or {}
        return slots.get(self._slot)

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def state(self) -> str:
        return STATE_PLAYING if self._scene else STATE_IDLE

    @property
    def media_title(self) -> str:
        # Occupied ⇒ real title; empty ⇒ the fixed placeholder.
        return slot_title(self._scene, SLOT_EMPTY_TITLE)

    @property
    def media_artist(self) -> str | None:
        return slot_performers(self._scene, SLOT_EMPTY_TITLE) if self._scene else None

    @property
    def media_album_name(self) -> str | None:
        return slot_studio(self._scene, SLOT_EMPTY_TITLE) if self._scene else None

    @property
    def media_content_id(self) -> str | None:
        scene = self._scene
        sid = scene.get("id") if scene else None
        return str(sid) if sid is not None else None

    @property
    def media_image_url(self) -> str | None:
        return slot_cover_url(self._scene)

    def _resolve_cover_entity(self) -> str | None:
        if self._cover_entity_id:
            return self._cover_entity_id
        if self.hass is None:
            return None
        cover_uid = unique_id(MODULE_ID, self._entry.entry_id, uid_slot_cover(self._slot))
        registry = er.async_get(self.hass)
        self._cover_entity_id = registry.async_get_entity_id("image", DOMAIN, cover_uid)
        return self._cover_entity_id

    @property
    def entity_picture(self) -> str | None:
        if not self._scene:
            return None
        cover = self._resolve_cover_entity()
        if cover and self.hass is not None:
            cover_state = self.hass.states.get(cover)
            if cover_state is not None:
                pic = cover_state.attributes.get("entity_picture")
                if pic:
                    return pic
        return self.media_image_url

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        scene = self._scene
        if not scene:
            return {"slot": self._slot, "scene_id": None}
        studio = scene.get("studio") or {}
        performers = scene.get("performers") or []
        tags = scene.get("tags") or []
        scene_id = scene.get("id")
        return {
            "slot": self._slot,
            "scene_id": str(scene_id) if scene_id is not None else None,
            "title": scene.get("title"),
            "studio": studio.get("name"),
            "performers": [p.get("name") for p in performers if p.get("name")],
            "tags": [t.get("name") for t in tags if t.get("name")],
            "cover_url": (scene.get("paths") or {}).get("screenshot"),
            "last_played_at": scene.get("last_played_at"),
            "resume_time": scene.get("resume_time"),
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._resolve_cover_entity()
