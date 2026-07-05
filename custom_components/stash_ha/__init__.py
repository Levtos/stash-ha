"""Stash HA standalone Home Assistant integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.core import ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from ._spec import SPEC
from .client import StashClient
from .const import (
    CONF_API_KEY,
    CONF_POLL_INTERVAL,
    CONF_URL,
    CONF_USE_WEBHOOK,
    DATA_ENTRIES,
    DATA_SERVICES_REGISTERED,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    MODULE_ID,
    service_name,
)
from .coordinator import StashLibraryCoordinator, StashPlaybackCoordinator
from .entities import async_get_entities  # re-export
from .flow import ConfigFlowHelper, OptionsFlowHelper  # re-export
from .services_impl import SERVICES  # re-export
from .webhook import StashWebhookView

_LOGGER = logging.getLogger(__name__)

PLATFORMS: tuple[Platform, ...] = (Platform.SENSOR, Platform.IMAGE, Platform.MEDIA_PLAYER)

__all__ = [
    "SPEC",
    "SERVICES",
    "ConfigFlowHelper",
    "OptionsFlowHelper",
    "async_setup_entry",
    "async_unload_entry",
    "async_get_entities",
]


async def async_setup(hass: HomeAssistant, _config: ConfigType) -> bool:
    hass.data.setdefault(
        DOMAIN,
        {DATA_ENTRIES: {}, DATA_SERVICES_REGISTERED: False},
    )
    await _async_register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(
        DOMAIN,
        {DATA_ENTRIES: {}, DATA_SERVICES_REGISTERED: False},
    )
    session = async_get_clientsession(hass)
    graphql_url: str = entry.data[CONF_URL]
    api_key: str = entry.data.get(CONF_API_KEY, "") or ""

    client = StashClient(graphql_url, session, api_key)
    poll_interval = int(entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL))
    playback = StashPlaybackCoordinator(hass, client, entry, poll_interval)
    library = StashLibraryCoordinator(hass, client, entry)

    try:
        await playback.async_config_entry_first_refresh()
        await library.async_config_entry_first_refresh()
    except Exception as err:  # noqa: BLE001
        raise ConfigEntryNotReady(str(err)) from err

    bucket = hass.data[DOMAIN][DATA_ENTRIES].setdefault(entry.entry_id, {})
    bucket["module_id"] = MODULE_ID
    runtime = {
        "client": client,
        "playback": playback,
        "library": library,
    }
    bucket["runtime"] = runtime

    if entry.options.get(CONF_USE_WEBHOOK, False):
        view = StashWebhookView(hass, entry.entry_id)
        hass.http.register_view(view)
        runtime["webhook_view"] = view

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info("Stash HA connected to %s", graphql_url)
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entry when options change so poll_interval / webhook take effect."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False
    bucket = hass.data.get(DOMAIN, {}).get(DATA_ENTRIES, {}).get(entry.entry_id)
    if bucket:
        bucket.pop("runtime", None)
    return True


async def _async_register_services(hass: HomeAssistant) -> None:
    if hass.data[DOMAIN].get(DATA_SERVICES_REGISTERED):
        return

    for action, sdef in SERVICES.items():
        full = service_name(MODULE_ID, action)
        if hass.services.has_service(DOMAIN, full):
            continue

        async def _handle(call: ServiceCall, _handler=sdef.handler) -> Any:
            return await _handler(hass, call)

        hass.services.async_register(DOMAIN, full, _handle, schema=sdef.schema)
        _LOGGER.debug("registered service %s.%s", DOMAIN, full)

    hass.data[DOMAIN][DATA_SERVICES_REGISTERED] = True
