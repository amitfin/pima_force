"""The Pima Force integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import homeassistant.helpers.config_validation as cv
import probatio
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_CONFIG_ENTRY_ID,
    CONF_NAME,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import ServiceResponse, SupportsResponse, callback
from homeassistant.exceptions import ConfigEntryNotReady, ServiceValidationError
from homeassistant.helpers import selector

from .const import (
    CONF_ZONES,
    DOMAIN,
    SERVICE_GET_ZONES,
    SERVICE_SET_ZONES,
)
from .coordinator import PimaForceDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.core import Event, HomeAssistant, ServiceCall
    from homeassistant.helpers.typing import ConfigType


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = (Platform.BINARY_SENSOR,)
SERVICE_GET_ZONES_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_CONFIG_ENTRY_ID): selector.ConfigEntrySelector(
            selector.ConfigEntrySelectorConfig(integration=DOMAIN)
        )
    }
)
SERVICE_SET_ZONES_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_CONFIG_ENTRY_ID): selector.ConfigEntrySelector(
            selector.ConfigEntrySelectorConfig(integration=DOMAIN)
        ),
        probatio.Required(CONF_ZONES): probatio.All(cv.ensure_list, [cv.string]),
    }
)


@dataclass
class PimaForceRuntimeData:
    """Pima Force runtime data dataclass."""

    coordinator: PimaForceDataUpdateCoordinator


type PimaForceConfigEntry = ConfigEntry[PimaForceRuntimeData]


@callback
def _async_get_config_entry(hass: HomeAssistant, entry_id: str) -> ConfigEntry:
    """Return the integration's config entry or raise if it doesn't exist."""
    config_entry = hass.config_entries.async_get_entry(entry_id)
    if config_entry is None or config_entry.domain != DOMAIN:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_config_entry",
            translation_placeholders={"entry_id": entry_id},
        )
    return config_entry


async def async_setup(hass: HomeAssistant, _: ConfigType) -> bool:
    """Set up the integration."""

    @callback
    def async_get_zones(call: ServiceCall) -> ServiceResponse:
        """Return zone list."""
        config_entry = _async_get_config_entry(hass, call.data[ATTR_CONFIG_ENTRY_ID])
        return {
            CONF_ZONES: [
                zone.get(CONF_NAME, "")
                for zone in config_entry.options.get(CONF_ZONES, [])
            ]
        }

    @callback
    def async_set_zones(call: ServiceCall) -> None:
        """Set zone list for a config entry."""
        config_entry = _async_get_config_entry(hass, call.data[ATTR_CONFIG_ENTRY_ID])
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
    coordinator = PimaForceDataUpdateCoordinator(hass, entry)
    entry.runtime_data = PimaForceRuntimeData(coordinator)
    try:
        await coordinator.async_start()
    except OSError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_listen",
            translation_placeholders={
                "port": str(entry.options[CONF_PORT]),
                "error": str(err),
            },
        ) from err
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        # The entry isn't unloaded when setup fails, so release the port here.
        await coordinator.async_stop()
        raise

    async def _async_stop(_: Event) -> None:
        await coordinator.async_stop()

    # Entries aren't unloaded when Home Assistant stops, so stop the server here.
    entry.async_on_unload(hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, _async_stop))
    return True


async def config_entry_update_listener(
    hass: HomeAssistant, entry: PimaForceConfigEntry
) -> None:
    """Update listener, called when the config entry options are changed."""
    hass.config_entries.async_schedule_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: PimaForceConfigEntry) -> bool:
    """Unload a config entry."""
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.coordinator.async_stop()
    return unloaded
