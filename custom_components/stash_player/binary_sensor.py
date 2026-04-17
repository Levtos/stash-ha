"""Online/offline binary sensor for Stash Player."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
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
    """Set up online binary sensor."""
    coordinator: StashLibraryCoordinator = hass.data[DOMAIN][entry.entry_id][LIBRARY_COORDINATOR_KEY]
    async_add_entities([StashOnlineBinarySensor(coordinator, entry)])


class StashOnlineBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor showing whether Stash is reachable."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: StashLibraryCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        player_name = entry.options.get(CONF_PLAYER_NAME, DEFAULT_PLAYER_NAME)
        self._attr_unique_id = f"{entry.entry_id}_online"
        self._attr_name = "Online"
        self._attr_icon = "mdi:lan-connect"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=player_name,
            manufacturer="Stash",
        )

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.last_update_success)
