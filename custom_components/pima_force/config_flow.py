"""Config flow for the Pima Force integration."""

from __future__ import annotations

from typing import Any

import homeassistant.helpers.config_validation as cv
import probatio
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

OPTIONS_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_PORT, default=DEFAULT_LISTENING_PORT): cv.positive_int,
        probatio.Optional(CONF_ZONES): ZONES_SCHEMA,
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

        self._async_abort_entries_match({CONF_PORT: user_input[CONF_PORT]})
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
        errors: dict[str, str] = {}
        if user_input is not None:
            if self._port_in_use(user_input[CONF_PORT]):
                errors[CONF_PORT] = "already_configured"
            else:
                if self._config_entry.options[CONF_PORT] != user_input[CONF_PORT]:
                    self.hass.config_entries.async_update_entry(
                        self._config_entry, title=f"{TITLE} {user_input[CONF_PORT]}"
                    )
                return self.async_create_entry(
                    data={**self._config_entry.options, **user_input},
                )

        values = {**self._config_entry.options, **(user_input or {})}
        return self.async_show_form(
            step_id="init",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_PORT, default=values[CONF_PORT]
                    ): cv.positive_int,
                    probatio.Optional(
                        CONF_ZONES, default=values.get(CONF_ZONES)
                    ): ZONES_SCHEMA,
                }
            ),
            errors=errors,
        )

    def _port_in_use(self, port: int) -> bool:
        """Return whether another entry of this integration uses the port."""
        return any(
            entry.options.get(CONF_PORT) == port
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if entry.entry_id != self._config_entry.entry_id
        )
