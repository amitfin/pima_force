"""Support for representing pima force entity."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_MANUFACTURER, DEVICE_MODEL, DEVICE_NAME, DOMAIN
from .coordinator import PimaForceDataUpdateCoordinator

if TYPE_CHECKING:
    from . import PimaForceConfigEntry


class PimaForceEntity(CoordinatorEntity[PimaForceDataUpdateCoordinator]):
    """Base class for entities."""

    _attr_has_entity_name = True

    def __init__(self, config_entry: PimaForceConfigEntry) -> None:
        """Initialize the entity."""
        super().__init__(config_entry.runtime_data.coordinator)
        self._config_entry = config_entry
        self._attr_device_info = DeviceInfo(
            name=DEVICE_NAME,
            manufacturer=DEVICE_MANUFACTURER,
            model=DEVICE_MODEL,
            identifiers={(DOMAIN, config_entry.entry_id)},
        )
