"""Sensor platform for Stash Player integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import StashCoordinator
from .const import COORDINATOR_KEY, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Stash sensors."""
    data: dict[str, Any] = hass.data[DOMAIN][entry.entry_id]
    coordinator: StashCoordinator = data[COORDINATOR_KEY]

    entities: list[BaseStashSensor] = [
        StashScenesSensor(coordinator, entry),
        StashMoviesSensor(coordinator, entry),
        StashPerformersSensor(coordinator, entry),
        StashStudiosSensor(coordinator, entry),
        StashTagsSensor(coordinator, entry),
        StashImagesSensor(coordinator, entry),
        StashGalleriesSensor(coordinator, entry),
        StashMarkersSensor(coordinator, entry),
        StashVersionSensor(coordinator, entry),
    ]

    async_add_entities(entities)


class BaseStashSensor(CoordinatorEntity, SensorEntity):
    """Base sensor for Stash counters."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: StashCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Stash",
            manufacturer="Stash",
        )


class StashScenesSensor(BaseStashSensor):
    """Sensor for total scenes count."""

    def __init__(self, coordinator: StashCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_scenes_count"
        self._attr_name = "Scenes Count"
        self._attr_icon = "mdi:filmstrip"
        self._attr_native_unit_of_measurement = "items"

    @property
    def native_value(self) -> int | None:
        data = self.coordinator.data or {}
        return data.get("scenes")


class StashMoviesSensor(BaseStashSensor):
    """Sensor for total movies/groups count."""

    def __init__(self, coordinator: StashCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_movies_count"
        self._attr_name = "Movies/Groups Count"
        self._attr_icon = "mdi:movie-open-outline"
        self._attr_native_unit_of_measurement = "items"

    @property
    def native_value(self) -> int | None:
        data = self.coordinator.data or {}
        return data.get("movies")


class StashPerformersSensor(BaseStashSensor):
    """Sensor for performers count."""

    def __init__(self, coordinator: StashCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_performers_count"
        self._attr_name = "Performers Count"
        self._attr_icon = "mdi:account-multiple"
        self._attr_native_unit_of_measurement = "items"

    @property
    def native_value(self) -> int | None:
        data = self.coordinator.data or {}
        return data.get("performers")


class StashStudiosSensor(BaseStashSensor):
    """Sensor for studios count."""

    def __init__(self, coordinator: StashCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_studios_count"
        self._attr_name = "Studios Count"
        self._attr_icon = "mdi:office-building"
        self._attr_native_unit_of_measurement = "items"

    @property
    def native_value(self) -> int | None:
        data = self.coordinator.data or {}
        return data.get("studios")


class StashTagsSensor(BaseStashSensor):
    """Sensor for tags count."""

    def __init__(self, coordinator: StashCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_tags_count"
        self._attr_name = "Tags Count"
        self._attr_icon = "mdi:tag-multiple"
        self._attr_native_unit_of_measurement = "items"

    @property
    def native_value(self) -> int | None:
        data = self.coordinator.data or {}
        return data.get("tags")


class StashImagesSensor(BaseStashSensor):
    """Sensor for single images count."""

    def __init__(self, coordinator: StashCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_images_count"
        self._attr_name = "Images Count"
        self._attr_icon = "mdi:image-multiple-outline"
        self._attr_native_unit_of_measurement = "items"

    @property
    def native_value(self) -> int | None:
        data = self.coordinator.data or {}
        return data.get("images")


class StashGalleriesSensor(BaseStashSensor):
    """Sensor for galleries count."""

    def __init__(self, coordinator: StashCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_galleries_count"
        self._attr_name = "Galleries Count"
        self._attr_icon = "mdi:image-album"
        self._attr_native_unit_of_measurement = "items"

    @property
    def native_value(self) -> int | None:
        data = self.coordinator.data or {}
        return data.get("galleries")


class StashMarkersSensor(BaseStashSensor):
    """Sensor for scene markers count."""

    def __init__(self, coordinator: StashCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_markers_count"
        self._attr_name = "Markers Count"
        self._attr_icon = "mdi:bookmark-multiple-outline"
        self._attr_native_unit_of_measurement = "items"

    @property
    def native_value(self) -> int | None:
        data = self.coordinator.data or {}
        return data.get("markers")


class StashVersionSensor(BaseStashSensor):
    """Sensor for Stash version string."""

    def __init__(self, coordinator: StashCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_version"
        self._attr_name = "Version"
        self._attr_icon = "mdi:information-outline"

    @property
    def native_value(self) -> str | None:
        data = self.coordinator.data or {}
        return data.get("version")
