"""Config flow for Stash HA."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN
from .flow import ConfigFlowHelper, OptionsFlowHelper


class StashHAConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._helper: ConfigFlowHelper | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if self._helper is None:
            self._helper = ConfigFlowHelper(self.hass, self)
        return await self._helper.async_step_module_step(user_input)

    async def async_step_module_step(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        return await self.async_step_user(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return StashHAOptionsFlow()


class StashHAOptionsFlow(OptionsFlow):
    def __init__(self) -> None:
        self._helper: OptionsFlowHelper | None = None

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if self._helper is None:
            self._helper = OptionsFlowHelper(self.hass, self.config_entry, self)
        return await self._helper.async_step_init(user_input)
