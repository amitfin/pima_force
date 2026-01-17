"""Config flow for the Pima Force integration."""

from __future__ import annotations

from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import CONF_ZONES, DEFAULT_LISTENING_PORT, DOMAIN, TITLE

ZONES_SCHEMA = selector.ObjectSelector(
    selector.ObjectSelectorConfig(
        multiple=True,
        translation_key="zone",
        fields={
            CONF_NAME: selector.ObjectSelectorField(
                selector=selector.TextSelector().serialize()["selector"]
            ),
        },
    )
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PORT, default=DEFAULT_LISTENING_PORT): cv.positive_int,
        vol.Optional(CONF_ZONES): ZONES_SCHEMA,
    }
)


class PimaForceConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Pima Force."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=OPTIONS_SCHEMA)

        return self.async_create_entry(
            title=f"{TITLE} {user_input[CONF_PORT]}",
            data={},
            options=user_input,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(OptionsFlow):
    """Handles options flow for the component."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Handle an options flow."""
        if user_input is not None:
            if self._config_entry.options[CONF_PORT] != user_input[CONF_PORT]:
                self.hass.config_entries.async_update_entry(
                    self._config_entry, title=f"{TITLE} {user_input[CONF_PORT]}"
                )
            return self.async_create_entry(
                data={**self._config_entry.options, **user_input},
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PORT, default=self._config_entry.options[CONF_PORT]
                    ): cv.positive_int,
                    vol.Optional(
                        CONF_ZONES, default=self._config_entry.options.get(CONF_ZONES)
                    ): ZONES_SCHEMA,
                }
            ),
        )
