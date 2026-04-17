"""Library statistics sensors for Stash Player."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_PLAYER_NAME, DEFAULT_PLAYER_NAME, DOMAIN, LIBRARY_COORDINATOR_KEY
from . import StashLibraryCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up library stat sensors."""
    coordinator: StashLibraryCoordinator = hass.data[DOMAIN][entry.entry_id][LIBRARY_COORDINATOR_KEY]
    async_add_entities([
        StashScenesSensor(coordinator, entry),
        StashMoviesSensor(coordinator, entry),
        StashPerformersSensor(coordinator, entry),
        StashStudiosSensor(coordinator, entry),
        StashTagsSensor(coordinator, entry),
        StashImagesSensor(coordinator, entry),
        StashGalleriesSensor(coordinator, entry),
        StashMarkersSensor(coordinator, entry),
        StashVersionSensor(coordinator, entry),
    ])


class _BaseStashSensor(CoordinatorEntity, SensorEntity):
    """Base class for Stash library sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: StashLibraryCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        player_name = entry.options.get(CONF_PLAYER_NAME, DEFAULT_PLAYER_NAME)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=player_name,
            manufacturer="Stash",
        )


class StashScenesSensor(_BaseStashSensor):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_scenes_count"
        self._attr_name = "Scenes"
        self._attr_icon = "mdi:filmstrip"
        self._attr_native_unit_of_measurement = "items"

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get("scenes")


class StashMoviesSensor(_BaseStashSensor):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_movies_count"
        self._attr_name = "Movies"
        self._attr_icon = "mdi:movie-open-outline"
        self._attr_native_unit_of_measurement = "items"

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get("movies")


class StashPerformersSensor(_BaseStashSensor):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_performers_count"
        self._attr_name = "Performers"
        self._attr_icon = "mdi:account-multiple"
        self._attr_native_unit_of_measurement = "items"

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get("performers")


class StashStudiosSensor(_BaseStashSensor):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_studios_count"
        self._attr_name = "Studios"
        self._attr_icon = "mdi:office-building"
        self._attr_native_unit_of_measurement = "items"

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get("studios")


class StashTagsSensor(_BaseStashSensor):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_tags_count"
        self._attr_name = "Tags"
        self._attr_icon = "mdi:tag-multiple"
        self._attr_native_unit_of_measurement = "items"

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get("tags")


class StashImagesSensor(_BaseStashSensor):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_images_count"
        self._attr_name = "Images"
        self._attr_icon = "mdi:image-multiple-outline"
        self._attr_native_unit_of_measurement = "items"

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get("images")


class StashGalleriesSensor(_BaseStashSensor):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_galleries_count"
        self._attr_name = "Galleries"
        self._attr_icon = "mdi:image-album"
        self._attr_native_unit_of_measurement = "items"

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get("galleries")


class StashMarkersSensor(_BaseStashSensor):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_markers_count"
        self._attr_name = "Markers"
        self._attr_icon = "mdi:bookmark-multiple-outline"
        self._attr_native_unit_of_measurement = "items"

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get("markers")


class StashVersionSensor(_BaseStashSensor):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_version"
        self._attr_name = "Version"
        self._attr_icon = "mdi:information-outline"

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get("version")
