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
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector

from .binary_sensor import zone_entity_id
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
        probatio.Required(CONF_PORT, default=DEFAULT_LISTENING_PORT): cv.port,
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
    def async_get_options_flow(_: ConfigEntry) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlow):
    """Handles options flow for the component."""

    _options: dict[str, Any]

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle an options flow."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if self._port_in_use(user_input[CONF_PORT]):
                errors[CONF_PORT] = "already_configured"
            else:
                self._options = {**self.config_entry.options, **user_input}
                if self._entity_renames():
                    return await self.async_step_confirm_port_change()
                return self._async_save()

        values = {**self.config_entry.options, **(user_input or {})}
        return self.async_show_form(
            step_id="init",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_PORT, default=values[CONF_PORT]): cv.port,
                    probatio.Optional(
                        CONF_ZONES, default=values.get(CONF_ZONES)
                    ): ZONES_SCHEMA,
                }
            ),
            errors=errors,
        )

    async def async_step_confirm_port_change(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a port change, which renames the zone entities."""
        renames = self._entity_renames()
        if user_input is not None:
            registry = er.async_get(self.hass)
            for entity_id, new_entity_id, _ in renames:
                registry.async_update_entity(entity_id, new_entity_id=new_entity_id)
            return self._async_save()

        entity_id, new_entity_id, name = renames[0]
        return self.async_show_form(
            step_id="confirm_port_change",
            description_placeholders={
                "old_port": str(self.config_entry.options[CONF_PORT]),
                "new_port": str(self._options[CONF_PORT]),
                "name": name,
                "old_entity_id": entity_id,
                "new_entity_id": new_entity_id,
            },
        )

    def _entity_renames(self) -> list[tuple[str, str, str]]:
        """
        Return (entity ID, new entity ID, zone name) for zones to rename.

        Only entities that still have the default entity ID of the old port are
        renamed, so entity IDs customized by the user are kept.
        """
        old_port = self.config_entry.options[CONF_PORT]
        new_port = self._options[CONF_PORT]
        if old_port == new_port:
            return []
        registry = er.async_get(self.hass)
        renames = []
        for index, zone in enumerate(self._options.get(CONF_ZONES, [])):
            if not zone.get(CONF_NAME):
                continue
            entity_id = zone_entity_id(old_port, index + 1)
            new_entity_id = zone_entity_id(new_port, index + 1)
            if (
                (entity := registry.async_get(entity_id)) is not None
                and entity.config_entry_id == self.config_entry.entry_id
                and registry.async_get(new_entity_id) is None
            ):
                renames.append((entity_id, new_entity_id, zone[CONF_NAME]))
        return renames

    @callback
    def _async_save(self) -> ConfigFlowResult:
        """Save the options, updating the title if the port changed."""
        if self.config_entry.options[CONF_PORT] != self._options[CONF_PORT]:
            # Update both at once, so the entry is reloaded only once.
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                title=f"{TITLE} {self._options[CONF_PORT]}",
                options=self._options,
            )
        return self.async_create_entry(data=self._options)

    def _port_in_use(self, port: int) -> bool:
        """Return whether another entry of this integration uses the port."""
        return any(
            entry.options.get(CONF_PORT) == port
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if entry.entry_id != self.config_entry.entry_id
        )
