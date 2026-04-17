"""Config flow for Stash Player."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import aiohttp_client, selector

from .const import (
    CONF_NSFW_MODE,
    CONF_DEBUG_LOGGING,
    CONF_PLAYER_NAME,
    CONF_POLL_INTERVAL,
    CONF_STASH_URL,
    CONF_USE_WEBHOOK,
    CONF_WEBHOOK_PORT,
    DEFAULT_NSFW_MODE,
    DEFAULT_DEBUG_LOGGING,
    DEFAULT_PLAYER_NAME,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_USE_WEBHOOK,
    DEFAULT_WEBHOOK_PORT,
    DOMAIN,
    NSFW_MODES,
)
from .graphql import (
    StashConnectionError,
    StashGraphQLClient,
    StashInvalidURLError,
    normalize_stash_url,
)


class StashPlayerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for Stash Player."""

    VERSION = 1

    def __init__(self) -> None:
        self._connection_data: dict[str, Any] = {}
        self._options_data: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Step 1: validate connection against Stash GraphQL endpoint."""
        errors: dict[str, str] = {}

        if user_input is not None:
            stash_url = user_input[CONF_STASH_URL]
            api_key = user_input[CONF_API_KEY]
            session = aiohttp_client.async_get_clientsession(self.hass)

            try:
                normalized_url = normalize_stash_url(stash_url)
            except StashInvalidURLError:
                errors["base"] = "invalid_url"
                normalized_url = stash_url

            client = StashGraphQLClient(session, normalized_url, api_key) if not errors else None

            if client is not None:
                try:
                    await client.validate_connection()
                except StashInvalidURLError:
                    errors["base"] = "invalid_url"
                except StashConnectionError:
                    errors["base"] = "cannot_connect"
                except ConfigEntryAuthFailed:
                    errors["base"] = "invalid_auth"
                except Exception:
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(normalized_url.lower())
                    self._abort_if_unique_id_configured()
                    self._connection_data = {
                        CONF_STASH_URL: normalized_url,
                        CONF_API_KEY: api_key.strip(),
                    }
                    return await self.async_step_options()

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_STASH_URL,
                    default="http://192.168.178.113:9999",
                ): selector.TextSelector(),
                vol.Required(CONF_API_KEY): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_options(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Step 2: gather behavior options."""
        if user_input is not None:
            self._options_data = user_input
            if user_input.get(CONF_USE_WEBHOOK):
                return await self.async_step_webhook()
            return self._create_entry()

        schema = vol.Schema(
            {
                vol.Optional(CONF_PLAYER_NAME, default=DEFAULT_PLAYER_NAME): selector.TextSelector(),
                vol.Optional(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=2, max=60, step=1, mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Optional(CONF_USE_WEBHOOK, default=DEFAULT_USE_WEBHOOK): selector.BooleanSelector(),
                vol.Optional(CONF_DEBUG_LOGGING, default=DEFAULT_DEBUG_LOGGING): selector.BooleanSelector(),
                vol.Optional(CONF_NSFW_MODE, default=DEFAULT_NSFW_MODE): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=NSFW_MODES,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key=CONF_NSFW_MODE,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="options", data_schema=schema)

    async def async_step_webhook(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Optional webhook-specific settings."""
        if user_input is not None:
            self._options_data.update(user_input)
            return self._create_entry()

        schema = vol.Schema(
            {
                vol.Optional(CONF_WEBHOOK_PORT, default=DEFAULT_WEBHOOK_PORT): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=65535, step=1, mode=selector.NumberSelectorMode.BOX)
                ),
            }
        )
        return self.async_show_form(step_id="webhook", data_schema=schema)

    def _create_entry(self) -> FlowResult:
        self._options_data.setdefault(CONF_WEBHOOK_PORT, DEFAULT_WEBHOOK_PORT)
        self._options_data.setdefault(CONF_USE_WEBHOOK, DEFAULT_USE_WEBHOOK)
        title = self._options_data.get(CONF_PLAYER_NAME, DEFAULT_PLAYER_NAME)
        return self.async_create_entry(title=title, data=self._connection_data, options=self._options_data)

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return StashPlayerOptionsFlow(config_entry)


class StashPlayerOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Stash Player."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry
        self._options_data: dict[str, Any] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Edit base options."""
        if user_input is not None:
            self._options_data = user_input
            if user_input.get(CONF_USE_WEBHOOK):
                return await self.async_step_webhook()
            self._options_data.setdefault(CONF_WEBHOOK_PORT, DEFAULT_WEBHOOK_PORT)
            return self.async_create_entry(title="", data=self._options_data)

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_PLAYER_NAME,
                    default=options.get(CONF_PLAYER_NAME, DEFAULT_PLAYER_NAME),
                ): selector.TextSelector(),
                vol.Optional(
                    CONF_POLL_INTERVAL,
                    default=options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=2, max=60, step=1, mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Optional(
                    CONF_USE_WEBHOOK,
                    default=options.get(CONF_USE_WEBHOOK, DEFAULT_USE_WEBHOOK),
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_DEBUG_LOGGING,
                    default=options.get(CONF_DEBUG_LOGGING, DEFAULT_DEBUG_LOGGING),
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_NSFW_MODE,
                    default=options.get(CONF_NSFW_MODE, DEFAULT_NSFW_MODE),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=NSFW_MODES,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key=CONF_NSFW_MODE,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_webhook(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Edit webhook-specific options."""
        if user_input is not None:
            self._options_data.update(user_input)
            return self.async_create_entry(title="", data=self._options_data)

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_WEBHOOK_PORT,
                    default=options.get(CONF_WEBHOOK_PORT, DEFAULT_WEBHOOK_PORT),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=65535, step=1, mode=selector.NumberSelectorMode.BOX)
                ),
            }
        )
        return self.async_show_form(step_id="webhook", data_schema=schema)
