"""Update local files."""

from __future__ import annotations

from typing import TYPE_CHECKING

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from attr import dataclass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_CONFIG_ENTRY_ID, CONF_NAME, Platform
from homeassistant.core import ServiceResponse, SupportsResponse, callback
from homeassistant.helpers import selector

from custom_components.pima_force.const import (
    CONF_ZONES,
    DOMAIN,
    SERVICE_GET_ZONES,
    SERVICE_SET_ZONES,
)

from .coordinator import PimaForceDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall
    from homeassistant.helpers.typing import ConfigType


PLATFORMS = (Platform.BINARY_SENSOR,)
SERVICE_GET_ZONES_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): selector.ConfigEntrySelector(
            selector.ConfigEntrySelectorConfig(integration=DOMAIN)
        )
    }
)
SERVICE_SET_ZONES_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): selector.ConfigEntrySelector(
            selector.ConfigEntrySelectorConfig(integration=DOMAIN)
        ),
        vol.Required(CONF_ZONES): vol.All(cv.ensure_list, [cv.string]),
    }
)


@dataclass
class PimaForceRuntimeData:
    """Pima Force runtime data dataclass."""

    coordinator: PimaForceDataUpdateCoordinator


type PimaForceConfigEntry = ConfigEntry[PimaForceRuntimeData]


async def async_setup(hass: HomeAssistant, _: ConfigType) -> bool:
    """Set up the integration."""

    @callback
    async def async_get_zones(call: ServiceCall) -> ServiceResponse:
        """Return zone list."""
        if config_entry := hass.config_entries.async_get_entry(
            call.data[ATTR_CONFIG_ENTRY_ID]
        ):
            return {
                CONF_ZONES: [
                    zone.get(CONF_NAME, "")
                    for zone in config_entry.options.get(CONF_ZONES, [])
                ]
            }
        return None

    @callback
    async def async_set_zones(call: ServiceCall) -> None:
        """Set zone list for a config entry."""
        if config_entry := hass.config_entries.async_get_entry(
            call.data[ATTR_CONFIG_ENTRY_ID]
        ):
            hass.config_entries.async_update_entry(
                config_entry,
                options={
                    **config_entry.options,
                    CONF_ZONES: [{CONF_NAME: zone} for zone in call.data[CONF_ZONES]],
                },
            )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_ZONES,
        async_get_zones,
        schema=SERVICE_GET_ZONES_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_ZONES,
        async_set_zones,
        schema=SERVICE_SET_ZONES_SCHEMA,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: PimaForceConfigEntry) -> bool:
    """Set up entity from a config entry."""
    entry.async_on_unload(entry.add_update_listener(config_entry_update_listener))
    entry.runtime_data = PimaForceRuntimeData(
        PimaForceDataUpdateCoordinator(hass, entry)
    )
    await entry.runtime_data.coordinator.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def config_entry_update_listener(
    hass: HomeAssistant, entry: PimaForceConfigEntry
) -> None:
    """Update listener, called when the config entry options are changed."""
    hass.config_entries.async_schedule_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: PimaForceConfigEntry) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.coordinator.async_stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
