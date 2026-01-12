"""Update local files."""

from __future__ import annotations

from typing import TYPE_CHECKING

from attr import dataclass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform

from .coordinator import PimaForceDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


PLATFORMS = (Platform.BINARY_SENSOR,)


@dataclass
class PimaForceRuntimeData:
    """Pima Force runtime data dataclass."""

    coordinator: PimaForceDataUpdateCoordinator


type PimaForceConfigEntry = ConfigEntry[PimaForceRuntimeData]


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
